"""One atomic population/freeze reservation shared by all evaluation versions."""
import os
from pathlib import Path
from higgsml.artifacts import digest_json, read_json
from higgsml._manifest import canonical_json_bytes
from higgsml.errors import ResearchError, ResearchStateError


def claim_population(root, population_id, freeze_id):
    root=Path(root).resolve(strict=True)
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
