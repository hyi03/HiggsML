"""Download contract tests use no network, ROOT, or training dependencies."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from src import data_contract as contract


@pytest.fixture
def definition():
    path = Path(contract.__file__).parents[1] / 'config/datasets/atlas2020_4lep.json'
    return json.loads(path.read_bytes())


def encode(value):
    return json.dumps(value).encode()


@pytest.mark.parametrize('name', contract.DATASET_NAMES)
def test_shipped_definition(name):
    binding = contract.load_dataset(name)
    assert len(binding.members) == 2
    assert binding.mc_only
    assert all(m.filename == m.file_key for m in binding.members)
    assert binding.definition_sha256 == contract.APPROVED_DEFINITIONS[name][1]


def test_duplicate_keys():
    with pytest.raises(ValueError, match='duplicate'):
        contract.parse_definition(b'{"x":1,"x":2}', contract.DATASET_NAMES[0])


@pytest.mark.parametrize('name', ['../atlas2020_4lep', 'atlas2025_4lep', 'mixed', '', 'C:\\other'])
def test_unknown_name(name):
    with pytest.raises(ValueError, match='unknown dataset'):
        contract.load_dataset(name)


@pytest.mark.parametrize('field,value', [
    ('schema_version', 'training.v1'), ('dataset_name', 'atlas2025_exactly4lep'),
    ('release', '2025'), ('collection', 'exactly4lep'), ('mc_only', False),
    ('mc_only', 1), ('definition_revision', True), ('definition_revision', 0),
    ('unknown', 1), ('members', []), ('members', {}),
])
def test_invalid_dataset(definition, field, value):
    definition[field] = value
    with pytest.raises(ValueError):
        contract.parse_definition(encode(definition), contract.DATASET_NAMES[0])


@pytest.mark.parametrize('field,value', [
    ('role', 'zz'), ('label', 0), ('label', True), ('dsid', 700600),
    ('release', '2025'), ('collection', 'exactly4lep'), ('filename', '../file.root'),
    ('filename', 'other.root'), ('file_key', '../file.root'), ('file_id', 'wrong'),
    ('size_bytes', -1), ('size_bytes', 1.5), ('sha256', 'bad'),
    ('source_checksum', 'wrong'), ('tree', 'wrong'), ('entry_count', 0),
    ('download_url', 'https://example.com/file.root'), ('record_url', 'https://example.com'),
    ('unknown', 'value'),
])
def test_invalid_member(definition, field, value):
    definition['members'][0][field] = value
    with pytest.raises(ValueError):
        contract.parse_definition(encode(definition), contract.DATASET_NAMES[0])


@pytest.mark.parametrize('mutation', ['swap', 'duplicate_hash', 'duplicate_id', 'cross_release', 'extra', 'missing'])
def test_pair_rejection(definition, mutation):
    if mutation == 'swap': definition['members'].reverse()
    elif mutation == 'duplicate_hash': definition['members'][1]['sha256'] = definition['members'][0]['sha256']
    elif mutation == 'duplicate_id': definition['members'][1]['file_id'] = definition['members'][0]['file_id']
    elif mutation == 'cross_release': definition['members'][0] = vars(contract.load_dataset(contract.DATASET_NAMES[1]).members[0])
    elif mutation == 'extra': definition['members'].append(copy.deepcopy(definition['members'][0]))
    else: definition['members'].pop()
    with pytest.raises(ValueError):
        contract.parse_definition(encode(definition), contract.DATASET_NAMES[0])


def test_unapproved_bytes_even_when_semantically_equal(definition):
    with pytest.raises(ValueError, match='not approved'):
        contract.parse_definition(encode(definition), contract.DATASET_NAMES[0])


def test_valid_shape_modified_hash_still_rejected(definition):
    definition['members'][0]['sha256'] = 'a' * 64
    with pytest.raises(ValueError, match='not approved'):
        contract.parse_definition(encode(definition), contract.DATASET_NAMES[0])


def test_standard_library_only_from_foreign_cwd(tmp_path):
    script = Path(contract.__file__).resolve().parents[2] / 'scripts/init_data.py'
    code = (
        'import runpy,sys; ns=runpy.run_path(sys.argv[1]); '
        'ns["load_dataset"]("atlas2020_4lep"); '
        'assert not ({"torch","uproot","yaml","numpy"} & set(sys.modules))'
    )
    result = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(script)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
