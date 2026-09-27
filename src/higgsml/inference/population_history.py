"""One atomic population/freeze reservation shared by all evaluation versions."""
import os
from pathlib import Path
from higgsml.artifacts import digest_json, read_json, sha256_file
from higgsml._manifest import canonical_json_bytes
from higgsml.errors import ResearchError, ResearchStateError


HISTORY_DIRECTORIES = ('.research-claims', '.h4l-mass-off-v2-claims',
                       '.h4l-mass-off-v3-claims', '.h4l-population-access')


def _safe_path(path):
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ResearchError(f'unsafe history path: {path}')


def history_scope(root):
    """Resolve declared local/archived roots; never discover or open event files."""
    requested = Path(root).absolute()
    _safe_path(requested)
    root = requested.resolve()
    registry = next((parent / 'config/h4l_history_roots.json'
                     for parent in (root, *root.parents)
                     if (parent / 'config/h4l_history_roots.json').exists()), None)
    if registry is None:
        # Standalone workflows have a single, explicitly bounded history scope.
        return {'roots': [str(root)], 'registry': None}
    _safe_path(registry)
    value = read_json(registry)
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'roots'}
            or value['schema_version'] != 'h4l-history-roots-v1'
            or not isinstance(value['roots'], list) or not value['roots']):
        raise ResearchError('invalid history root registry')
    project = registry.parent.parent
    roots = []
    for entry in value['roots']:
        if (not isinstance(entry, dict) or set(entry) != {'path', 'required'}
                or not isinstance(entry['path'], str) or not entry['path']
                or type(entry['required']) is not bool):
            raise ResearchError('invalid history root entry')
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ResearchError('unsafe history root entry')
        candidate = project / relative
        _safe_path(candidate)
        candidate = candidate.resolve()
        if candidate == project or not candidate.is_relative_to(project) or str(candidate) in roots:
            raise ResearchError('invalid or duplicate history root')
        if (entry['required'] and not candidate.is_dir()) or (candidate.exists() and not candidate.is_dir()):
            raise ResearchError(f'required history root unavailable: {candidate}')
        roots.append(str(candidate))
    if str(root) not in roots:
        raise ResearchError(f'current history root is not registered: {root}')
    return {'roots': roots, 'registry': {'path': str(registry), 'sha256': sha256_file(registry)}}


def audit_population_history(root, *, population_id=None, prepared_id=None):
    """Fail closed on unknown history; model-self claims do not consume access."""
    scope = history_scope(root)
    matches = []
    for base in scope['roots']:
        for name in HISTORY_DIRECTORIES:
            directory = Path(base) / name
            _safe_path(directory)
            if not directory.exists():
                continue
            if not directory.is_dir():
                raise ResearchError(f'invalid history directory: {directory}')
            for path in sorted(directory.glob('*.json')):
                _safe_path(path)
                value = read_json(path)
                binding = value.get('binding', value) if isinstance(value, dict) else None
                if (not isinstance(binding, dict)
                        or not (binding.get('population_id') or binding.get('prepared_artifact_id'))):
                    raise ResearchError(f'invalid history identity: {path}')
                if binding.get('stage') == 'model-self':
                    continue
                if ((population_id is None and prepared_id is None)
                        or (population_id is not None and binding.get('population_id') == population_id)
                        or (prepared_id is not None and binding.get('prepared_artifact_id') == prepared_id)):
                    matches.append({'path': str(path.resolve()), 'sha256': sha256_file(path), 'claim': value})
    return {**scope, 'matches': matches, 'scope': 'declared_roots_only_not_independent_validation'}


def claim_population(root, population_id, freeze_id):
    root=Path(root).resolve(strict=True)
    audit = audit_population_history(root, population_id=population_id)
    for item in audit['matches']:
        binding = item['claim'].get('binding', item['claim'])
        if binding.get('freeze_artifact_id') != freeze_id:
            raise ResearchStateError('population previously used under another freeze',
                                     status='assessment_already_started')
    # All registered roots compete for one O_EXCL reservation, including when
    # evaluation is resumed from an archived root.
    root = Path(audit['roots'][0])
    root.mkdir(parents=True, exist_ok=True)
    directory=root/'.h4l-population-access'
    if directory.is_symlink() or directory.is_junction():
        raise ResearchError('unsafe population history directory')
    directory.mkdir(exist_ok=True)
    if not directory.is_dir() or directory.resolve().parent!=root:
        raise ResearchError('unsafe population history directory')
    value={'population_id':population_id,'freeze_artifact_id':freeze_id}
    path=directory/(digest_json(population_id)+'.json')
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        if path.is_symlink() or read_json(path)!=value:
            raise ResearchStateError('population previously used under another freeze',status='assessment_already_started')
        return
    with os.fdopen(fd,'wb') as stream:
        stream.write(canonical_json_bytes(value));stream.flush();os.fsync(stream.fileno())
