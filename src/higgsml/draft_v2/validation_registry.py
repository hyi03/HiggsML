"""Metadata-only planning, immutable source binding and supplemental access."""
import os
from pathlib import Path

from higgsml.artifacts import ResearchRun, digest_json, read_json, read_run
from higgsml.dataset_binding import dataset_context
from higgsml.errors import ResearchError
from higgsml.inference.population_history import audit_population_history, _safe_path
from higgsml.protocol import canonical
from higgsml.draft_v2.protocol import QUALIFICATION, candidate_keys, load_protocol as base_protocol
from higgsml.draft_v2.validation_protocol import EXPECTED, units
from higgsml.draft_v2 import workflow


def validate_protocol(protocol):
    if digest_json(protocol) != digest_json(EXPECTED):
        raise ResearchError('Unsupported supplemental protocol or budget')


def safe_roots(source, root):
    source, root = Path(source).absolute(), Path(root).absolute()
    _safe_path(source)
    _safe_path(root)
    source, root = source.resolve(), root.resolve()
    if source == root or source.parent != root.parent:
        raise ResearchError('Supplement output must be a new sibling of the source workflow')
    return source, root


def load_source(source, *, metadata_only=False):
    """Never verify/hash/open prepared event payload here, even in full mode."""
    source = Path(source)
    protocol = base_protocol(source / 'prepare/protocol.json')
    def load(name, stage):
        _safe_path(source/name)
        return read_run(source / name, dataset=protocol['dataset'], protocol=protocol,
                        stages=(f'draft-v2-{stage}',))
    prepared, frozen_run, report = load('prepare', 'prepare'), load('freeze', 'freeze'), load('report', 'report')
    metadata = prepared.read_json('population.json')
    if (metadata.get('schema_version') != 'h4l-draft-v2-population-v1'
            or metadata.get('source_kind') not in {'synthetic', 'controlled_mc'}
            or metadata.get('dataset_snapshot') != dataset_context(protocol['dataset']).snapshot()
            or metadata.get('historical_test_included') is not True
            or metadata.get('qualification') != QUALIFICATION
            or 'events.jsonl' not in prepared.manifest['files']):
        raise ResearchError('Invalid source population metadata')
    frozen = frozen_run.read_json('freeze.json')
    if (frozen.get('freeze_id') != digest_json({k: v for k, v in frozen.items() if k != 'freeze_id'})
            or set(frozen.get('models', {})) != set(candidate_keys())):
        raise ResearchError('Source freeze metadata seal mismatch')
    rb = report.read_json('binding.json')
    candidates = []
    for path in [source/'evaluate', *source.glob('evaluate-retry-*')]:
        if path.is_dir():
            # Select by the report's immutable binding, never by directory order.
            try:
                _safe_path(path)
                manifest = read_json(path/'manifest.json')
            except ResearchError:
                continue  # An unselected failed attempt is preserved, not promoted.
            if manifest.get('artifact_id') == rb.get('evaluation_artifact_id'):
                candidates.append(path)
    if len(candidates) != 1:
        raise ResearchError('Source report must select exactly one nominal evaluation')
    evaluation = load(candidates[0].name, 'evaluate')
    if rb != dict(evaluation_artifact_id=evaluation.manifest['artifact_id'],
                  freeze_artifact_id=frozen_run.manifest['artifact_id'],
                  prepared_artifact_id=prepared.manifest['artifact_id'], source_kind=metadata['source_kind']):
        raise ResearchError('Source report bindings mismatch')
    trained = {k: load('train/'+k.replace(':', '-'), 'train') for k in candidate_keys()}
    handles = [prepared, frozen_run, evaluation, report, *trained.values()]
    identity = dict(source_run=str(source.resolve()),
        artifacts={str(h.path.relative_to(source.resolve())): h.manifest['artifact_id'] for h in handles},
        prepared_artifact_id=prepared.manifest['artifact_id'], freeze_artifact_id=frozen_run.manifest['artifact_id'],
        freeze_id=frozen.get('freeze_id'), population_id=metadata['population_id'],
        model_ids={k: v['model_id'] for k, v in frozen.get('models', {}).items()},
        source_kind=metadata['source_kind'], base_protocol_sha256=digest_json(protocol),
        event_receipt=prepared.manifest['files']['events.jsonl'])
    result = dict(identity=identity, prepared=prepared, frozen=frozen, protocol=protocol, handles=handles)
    if metadata_only:
        return result
    workflow._validate_freeze(frozen_run, prepared, protocol)
    validated = workflow._evaluation(source, protocol, frozen_run, name=evaluation.path.name)
    nominal = validated.read_json('results.json')
    if (report.read_json('results.json') != nominal
            or report.read_json('summary.json') != workflow.summarize(nominal)):
        raise ResearchError('Source report aggregate mismatch')
    result['nominal'] = nominal
    result['models'] = {k: h.read_json('model.json') for k, h in trained.items()}
    return result


def new_run(root, name, stage, protocol, upstreams=()):
    return ResearchRun(Path(root)/name, allowed_root=root, stage='draft-v2-validation-'+stage,
                       dataset=protocol['dataset'], protocol=protocol, upstreams=list(upstreams),
                       context={'qualification': QUALIFICATION})


def load(root, name, stage, protocol):
    loaded = read_run(Path(root)/name, dataset=protocol['dataset'], protocol=protocol,
                      stages=('draft-v2-validation-'+stage,))
    for filename in loaded.manifest['files']:
        loaded.file(filename)
    return loaded


def history(root, registration_id):
    audit = audit_population_history(Path(root).parent)
    audit['matches'] = [m for m in audit['matches']
        if m['claim'].get('binding', m['claim']).get('registration_id') != registration_id]
    return audit


def access_template(root, registration):
    identity = registration['source']
    return dict(schema_version='h4l-draft-v2-validation-access-v1', status='pending', decision='pending',
        dataset=EXPECTED['dataset'], source_population='all_mc', independent=False,
        source_kind=identity['source_kind'], prepared_artifact_id=identity['prepared_artifact_id'],
        population_id=identity['population_id'], source_freeze_id=identity['freeze_id'],
        registration_id=registration['registration_id'], protocol_sha256=digest_json(EXPECTED),
        budget=dict(paired_replicas=200, modes=EXPECTED['bootstrap']['modes']),
        history_sha256=digest_json(history(root, registration['registration_id'])), reviewed_by='', reviewed_at='')


def registration_value(source, root, protocol):
    value = dict(schema_version='h4l-draft-v2-validation-registration-v1', source=source['identity'],
        output_root=str(Path(root).resolve()), protocol_sha256=digest_json(protocol),
        units=units(), budget=dict(bootstrap_interval_groups=6200, model_self_fits=24000),
        qualification=QUALIFICATION)
    return {**value, 'registration_id': digest_json(value)}


def plan(source_run, root, protocol):
    validate_protocol(protocol)
    source_run, root = safe_roots(source_run, root)
    source = load_source(source_run, metadata_only=True)
    value = registration_value(source, root, protocol)
    existing = {}
    for unit in units():
        paths = [root/'units'/unit, *sorted((root/'units').glob(unit+'-retry-*'))]
        existing[unit] = [str(p) for p in paths if p.exists()]
    return dict(mode='plan_only', registration=value, existing_units_unverified=existing,
        pending_units=[u for u, paths in existing.items() if not paths],
        access_review_template=access_template(root, value),
        access_requirements=['new supplemental plan-bound approval before bootstrap event access',
                             'durable claim before cache construction', 'model-self uses nominal aggregates only'],
        payloads_opened=False, completed_units_not_validated=True)


def register(source_run, root, protocol, *, continuation=False):
    validate_protocol(protocol)
    source_run, root = safe_roots(source_run, root)
    source = load_source(source_run)
    value = registration_value(source, root, protocol)
    if (root/'register').exists():
        if not continuation:
            raise ResearchError('Registration exists; use --continue')
        previous = load(root, 'register', 'register', protocol)
        if previous.read_json('registration.json') != value:
            raise ResearchError('Registration source, budget or output identity changed')
        return previous
    if root.exists():
        raise ResearchError('New registration requires a fresh output directory; preserve existing evidence')
    with new_run(root, 'register', 'register', protocol, source['handles']) as run:
        run.write_json('registration.json', value)
        run.write_json('base-protocol.json', source['protocol'])
        run.write_json('nominal.json', source['nominal'])
        run.write_json('access-review.pending.json', access_template(root, value))
    return load(root, 'register', 'register', protocol)


def bound_registration(source_run, root, protocol):
    validate_protocol(protocol)
    source_run, root = safe_roots(source_run, root)
    registered = load(root, 'register', 'register', protocol)
    source = load_source(source_run)
    value = registration_value(source, root, protocol)
    if registered.read_json('registration.json') != value or registered.read_json('nominal.json') != source['nominal']:
        raise ResearchError('Supplemental source binding changed')
    return registered, value, source


def atomic_claim(path, value, *, reuse=False):
    _safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        if reuse and read_json(path) == value:
            return
        raise ResearchError('Existing or changed access/unit claim; explicit recovery required') from error
    with os.fdopen(fd, 'wb') as output:
        output.write(canonical(value))
        output.flush()
        os.fsync(output.fileno())


def authorize(root, registered, registration, review_path):
    if review_path is None:
        raise ResearchError('Bootstrap requires a newly reviewed supplemental access receipt')
    review = read_json(Path(review_path))
    expected = access_template(root, registration)
    from jsonschema import Draft202012Validator
    schema = Path(__file__).resolve().parents[3]/'config/schemas/h4l_draft_v2_validation_access.schema.json'
    try:
        Draft202012Validator(read_json(schema)).validate(review)
    except Exception as error:
        raise ResearchError('Supplemental access receipt schema is incorrectly bound') from error
    if (set(review) != set(expected) or review.get('status') != 'approved'
            or review.get('decision') != 'allow_exploratory_supplement'
            or any(not isinstance(review.get(k), str) or not review[k].strip() for k in ('reviewed_by', 'reviewed_at'))
            or any(review[k] != v for k, v in expected.items()
                   if k not in {'status', 'decision', 'reviewed_by', 'reviewed_at'})):
        raise ResearchError('Supplemental access receipt is pending, stale or incorrectly bound')
    source = registration['source']
    binding = dict(registration_id=registration['registration_id'],
        freeze_artifact_id=registered.manifest['artifact_id'], source_freeze_artifact_id=source['freeze_artifact_id'],
        population_id=source['population_id'], prepared_artifact_id=source['prepared_artifact_id'],
        dataset=EXPECTED['dataset'], source_population='all_mc', source_kind=source['source_kind'],
        stage='draft-v2-validation-bootstrap', budget=expected['budget'], protocol_sha256=digest_json(EXPECTED))
    directory = Path(history(root, registration['registration_id'])['roots'][0])/'.h4l-draft-v2-validation-claims'
    path = directory/(registration['registration_id']+'.json')
    atomic_claim(path, {'binding': binding}, reuse=True)
    return dict(review=review, claim={'path': str(path), 'binding': binding})
