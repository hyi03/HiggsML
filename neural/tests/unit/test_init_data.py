"""Transactions use tiny bytes and mocked HTTP; never touch repository data."""
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/init_data.py'
spec = importlib.util.spec_from_file_location('tested_init_data', SCRIPT)
init = importlib.util.module_from_spec(spec)
spec.loader.exec_module(init)


class Response(io.BytesIO):
    status = 200
    headers = {}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    payloads = [b'higgs fixture', b'zz fixture']
    original = init.load_dataset
    bindings = {
        name: replace(original(name), members=tuple(
            replace(m, size_bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
            for m, b in zip(original(name).members, payloads, strict=True)
        )) for name in init.DATASET_NAMES
    }
    monkeypatch.setattr(init, 'load_dataset', bindings.__getitem__)
    monkeypatch.setattr(init.time, 'sleep', lambda _: None)
    calls = []
    def http(request, timeout):
        assert timeout == init.TIMEOUT
        calls.append(request.full_url)
        return Response(payloads[0 if '345060.' in request.full_url else 1])
    monkeypatch.setattr(init, 'urlopen', http)
    return tmp_path / 'data', bindings, payloads, calls


def pair_paths(setup, name=None):
    data, bindings, _, _ = setup
    binding = bindings[name or init.DATASET_NAMES[0]]
    directory = data / 'raw' / binding.dataset_name
    return binding, directory, directory / 'dataset_receipt.json'


def test_default_and_idempotence(setup):
    data, bindings, _, calls = setup
    init.initialize(data)
    assert len(calls) == 4
    snapshots = {}
    for name, binding in bindings.items():
        _, directory, receipt = pair_paths(setup, name)
        value = json.loads(receipt.read_bytes())
        assert value['status'] == 'complete'
        assert value['validation_scope'] == 'file_bytes_only'
        assert value['definition_sha256'] == binding.definition_sha256
        snapshots[name] = (receipt.read_bytes(), receipt.stat().st_mtime_ns)
        assert not (directory / '.init-data.lock').exists()
    init.initialize(data)
    assert len(calls) == 4
    for name in bindings:
        _, _, receipt = pair_paths(setup, name)
        assert (receipt.read_bytes(), receipt.stat().st_mtime_ns) == snapshots[name]


def test_selected_pair_only(setup):
    data, _, _, calls = setup
    init.initialize(data, dataset=init.DATASET_NAMES[1])
    assert len(calls) == 2
    assert not (data / 'raw' / init.DATASET_NAMES[0]).exists()


@pytest.mark.parametrize('bad', [b'x', b'wrong fixture'])
def test_corrupt_existing_invalidates_receipt_and_force_repairs(setup, bad):
    data, _, _, calls = setup
    binding, directory, receipt = pair_paths(setup)
    init.initialize(data, dataset=binding.dataset_name)
    target = directory / binding.members[0].filename
    target.write_bytes(bad)
    with pytest.raises(RuntimeError, match='--force'):
        init.initialize(data, dataset=binding.dataset_name)
    assert not receipt.exists()
    assert len(calls) == 2
    init.initialize(data, dataset=binding.dataset_name, force=True)
    assert receipt.exists()
    assert init.verify_file(target, binding.members[0])[0]


@pytest.mark.parametrize('failure', ['http', 'url', 'truncated', 'hash', 'oversize', 'status', 'read'])
def test_force_failure_preserves_complete_pair(setup, monkeypatch, failure):
    data, _, payloads, _ = setup
    binding, directory, receipt = pair_paths(setup)
    init.initialize(data, dataset=binding.dataset_name)
    before = receipt.read_bytes()
    attempts = []
    def fail(request, timeout):
        attempts.append(request)
        if failure == 'http': raise HTTPError(request.full_url, 503, 'unavailable', {}, None)
        if failure == 'url': raise URLError('offline')
        if failure == 'read':
            class Broken(Response):
                def read(self, size): raise ConnectionResetError('read failed')
            return Broken()
        if failure == 'status':
            response = Response(payloads[0]); response.status = 206; return response
        return Response({'truncated': b'x', 'hash': b'x'*len(payloads[0]),
                         'oversize': b'x'*100}[failure])
    monkeypatch.setattr(init, 'urlopen', fail)
    foreign = directory / '.another-call.part'; foreign.write_bytes(b'owned elsewhere')
    with pytest.raises(RuntimeError):
        init.initialize(data, dataset=binding.dataset_name, force=True)
    assert len(attempts) == init.MAX_ATTEMPTS
    assert receipt.read_bytes() == before
    assert all(init.verify_file(directory / m.filename, m)[0] for m in binding.members)
    assert list(directory.glob('*.part')) == [foreign]
    assert foreign.read_bytes() == b'owned elsewhere'


def test_partial_pair_recovers(setup, monkeypatch):
    data, _, _, _ = setup
    binding, directory, receipt = pair_paths(setup)
    original = init.urlopen
    def fail_background(request, timeout):
        if '363490' in request.full_url: raise URLError('offline')
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', fail_background)
    with pytest.raises(RuntimeError): init.initialize(data, dataset=binding.dataset_name)
    assert (directory / binding.members[0].filename).exists()
    assert not receipt.exists()
    monkeypatch.setattr(init, 'urlopen', original)
    init.initialize(data, dataset=binding.dataset_name)
    assert receipt.exists()


def test_default_continues_other_pair_on_failure(setup, monkeypatch):
    data, _, _, _ = setup
    original = init.urlopen
    def fail_2020(request, timeout):
        if '/15005/' in request.full_url: raise URLError('offline')
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', fail_2020)
    with pytest.raises(RuntimeError): init.initialize(data)
    assert pair_paths(setup, init.DATASET_NAMES[1])[2].exists()
    assert not pair_paths(setup)[2].exists()


def test_lock_conflict_and_foreign_lock_preserved(setup):
    data, _, _, calls = setup
    binding, directory, _ = pair_paths(setup)
    directory.mkdir(parents=True)
    with init.dataset_lock(directory):
        before = (directory / '.init-data.lock').read_bytes()
        with pytest.raises(RuntimeError, match='locked'):
            init.initialize(data, dataset=binding.dataset_name)
        assert (directory / '.init-data.lock').read_bytes() == before
        assert not calls
    assert not (directory / '.init-data.lock').exists()


def test_interruption_cleans_owned_temp(setup, monkeypatch):
    data, _, _, _ = setup
    binding, directory, receipt = pair_paths(setup)
    def interrupt(*args, **kwargs): raise KeyboardInterrupt()
    monkeypatch.setattr(init, 'urlopen', interrupt)
    with pytest.raises(KeyboardInterrupt): init.initialize(data, dataset=binding.dataset_name)
    assert not receipt.exists()
    assert not list(directory.glob('*.part'))
    assert not (directory / '.init-data.lock').exists()


@pytest.mark.parametrize('target', ['dataset', 'member', 'receipt', 'raw'])
def test_directory_disguise(setup, target):
    data, _, _, calls = setup
    binding, directory, receipt = pair_paths(setup)
    if target in {'member', 'receipt'}:
        directory.mkdir(parents=True)
        (receipt if target == 'receipt' else directory / binding.members[0].filename).mkdir()
    else:
        path = directory if target == 'dataset' else directory.parent
        path.parent.mkdir(parents=True); path.write_bytes(b'not a directory')
    with pytest.raises(RuntimeError): init.initialize(data, dataset=binding.dataset_name)
    assert not calls


@pytest.mark.parametrize('target', ['dataset', 'member', 'receipt'])
def test_symlink_rejected(setup, tmp_path, target):
    data, _, _, calls = setup
    binding, directory, receipt = pair_paths(setup)
    directory.mkdir(parents=True)
    outside = tmp_path / 'outside'; outside.mkdir()
    link = directory if target == 'dataset' else receipt if target == 'receipt' else directory / binding.members[0].filename
    if target == 'dataset': directory.rmdir()
    try: link.symlink_to(outside, target_is_directory=True)
    except OSError: pytest.skip('OS does not permit symlink creation')
    with pytest.raises(RuntimeError, match='link/reparse'): init.initialize(data, dataset=binding.dataset_name)
    assert not calls


def test_retry_reuses_matching_prefix_when_server_ignores_range(setup, monkeypatch, capsys):
    _, _, payloads, _ = setup
    binding, directory, _ = pair_paths(setup)
    directory.mkdir(parents=True)
    destination = directory / binding.members[0].filename
    monkeypatch.setattr(init, 'CHUNK_SIZE', 2)
    original = init.urlopen; count = 0
    def transient(request, timeout):
        nonlocal count
        count += 1
        if count == 1: return Response(payloads[0][:7])
        if count == 2: assert request.get_header('Range') == 'bytes=7-'
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', transient)
    init.download(binding.members[0], destination)
    assert count == 2
    assert destination.read_bytes() == payloads[0]
    output = capsys.readouterr().out
    assert 'server ignored Range; validating saved prefix' in output
    assert 'restarting from zero' not in output
    percentages = [float(value) for value in re.findall(r']\s+([0-9.]+)%', output)]
    assert percentages == sorted(percentages)
    assert not list(directory.glob('*.part'))


@pytest.mark.parametrize('failure', ['eof', 'reset', 'timeout'])
def test_retry_resumes_partial_transfer(setup, monkeypatch, failure):
    data, _, payloads, _ = setup
    binding, directory, receipt = pair_paths(setup)
    payload = payloads[0]
    requests = []
    original = init.urlopen
    class Interrupted(Response):
        def read(self, size):
            if self.tell() == 4 and failure != 'eof':
                raise (TimeoutError if failure == 'timeout' else ConnectionResetError)('interrupted')
            return super().read(size)
    def http(request, timeout):
        requests.append(request)
        assert request.get_header('Accept-encoding') == 'identity'
        if len(requests) == 1:
            return Interrupted(payload[:4])
        if len(requests) == 2:
            assert request.get_header('Range') == 'bytes=4-'
            response = Response(payload[4:])
            response.status = 206
            response.headers = {'Content-Range': f'bytes 4-{len(payload)-1}/{len(payload)}'}
            return response
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', http)
    init.initialize(data, dataset=binding.dataset_name)
    assert len(requests) == 3
    assert receipt.exists()
    assert (directory / binding.members[0].filename).read_bytes() == payload
    assert not list(directory.glob('*.part'))


@pytest.mark.parametrize('content_range', ['', 'bytes 0-12/13', 'bytes 4-12/99',
                                         'bytes 4-99/13', 'bytes 4-3/13'])
def test_invalid_resume_response_never_appended(setup, monkeypatch, content_range):
    data, _, payloads, _ = setup
    binding, directory, receipt = pair_paths(setup)
    original = init.urlopen
    count = 0
    def http(request, timeout):
        nonlocal count
        count += 1
        if count == 1: return Response(payloads[0][:4])
        if count == 2:
            response = Response(b'bad bytes')
            response.status = 206
            response.headers = {'Content-Range': content_range}
            return response
        if count == 3: assert request.get_header('Range') == 'bytes=4-'
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', http)
    init.initialize(data, dataset=binding.dataset_name)
    assert count == 4
    assert receipt.exists()


def test_hash_mismatch_retries_without_range(setup, monkeypatch):
    data, _, payloads, _ = setup
    binding, _, receipt = pair_paths(setup)
    original = init.urlopen
    count = 0
    def http(request, timeout):
        nonlocal count
        count += 1
        assert request.get_header('Range') is None
        if count == 1: return Response(b'x' * len(payloads[0]))
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', http)
    init.initialize(data, dataset=binding.dataset_name)
    assert receipt.exists()


def test_read_failure_after_full_body_restarts_safely(setup, monkeypatch):
    data, _, payloads, _ = setup
    binding, _, receipt = pair_paths(setup)
    original = init.urlopen
    count = 0
    class LateFailure(Response):
        def read(self, size):
            if self.tell() == len(payloads[0]):
                raise ConnectionResetError('late reset')
            return super().read(size)
    def http(request, timeout):
        nonlocal count
        count += 1
        assert request.get_header('Range') is None
        if count == 1: return LateFailure(payloads[0])
        return original(request, timeout)
    monkeypatch.setattr(init, 'urlopen', http)
    init.initialize(data, dataset=binding.dataset_name)
    assert count == 3
    assert receipt.exists()


@pytest.mark.parametrize('content', [b'{}', b'invalid', b'[]', b'{"status":"complete","status":"complete"}'])
def test_stale_receipt_rebuilt(setup, content):
    data, _, _, calls = setup
    binding, directory, receipt = pair_paths(setup)
    init.initialize(data, dataset=binding.dataset_name)
    receipt.write_bytes(content)
    init.initialize(data, dataset=binding.dataset_name)
    assert len(calls) == 2
    assert json.loads(receipt.read_bytes())['status'] == 'complete'


def test_cli_and_exit_codes(setup, monkeypatch):
    data, _, _, _ = setup
    assert init.parse_args([]).dataset is None
    for args in [['--dataset', 'mixed'], ['--dataset-pair', 'atlas2020_4lep']]:
        with pytest.raises(SystemExit) as error: init.parse_args(args)
        assert error.value.code == 2
    monkeypatch.setattr(init, 'REPOSITORY_ROOT', data.parent)
    assert init.main(['--dataset', init.DATASET_NAMES[0]]) == 0
    def fail(*args, **kwargs): raise RuntimeError('failure')
    monkeypatch.setattr(init, 'initialize', fail)
    assert init.main([]) == 1


def test_cli_foreign_cwd(tmp_path):
    result = subprocess.run([sys.executable, '-I', '-S', str(SCRIPT), '--help'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0
    assert all(name in result.stdout for name in init.DATASET_NAMES)


def test_no_legacy_file_fallback(setup):
    data, _, _, calls = setup
    (data / 'raw').mkdir(parents=True)
    old = data / 'raw/higgs.root'; old.write_bytes(b'legacy')
    init.initialize(data)
    assert len(calls) == 4
    assert old.read_bytes() == b'legacy'


def test_parent_traversal_rejected(tmp_path):
    with pytest.raises(RuntimeError, match='traversal'):
        init.safe_path(tmp_path / 'inside' / '..' / 'outside')


def test_receipt_publication_failure_recovers(setup, monkeypatch):
    data, _, _, calls = setup
    binding, directory, receipt = pair_paths(setup)
    original = init.os.replace
    def fail_receipt(source, target):
        if target == receipt:
            raise OSError('publication interrupted')
        return original(source, target)
    monkeypatch.setattr(init.os, 'replace', fail_receipt)
    with pytest.raises(RuntimeError, match='publication interrupted'):
        init.initialize(data, dataset=binding.dataset_name)
    assert not receipt.exists()
    assert all(init.verify_file(directory / m.filename, m)[0] for m in binding.members)
    assert not list(directory.glob('*.part'))
    monkeypatch.setattr(init.os, 'replace', original)
    init.initialize(data, dataset=binding.dataset_name)
    assert receipt.exists()
    assert len(calls) == 2


def test_reparse_attribute_rejected(tmp_path, monkeypatch):
    target = tmp_path / 'junction'
    target.mkdir()
    original = Path.lstat
    def reparse(path):
        info = original(path)
        if path == target:
            from types import SimpleNamespace
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path, 'lstat', reparse)
    with pytest.raises(RuntimeError, match='reparse'):
        init.safe_path(target, directory=True)


def test_another_process_cannot_acquire_lock(setup):
    _, _, _, _ = setup
    _, directory, _ = pair_paths(setup)
    directory.mkdir(parents=True)
    code = ('import runpy,sys; from pathlib import Path; '
            'ns=runpy.run_path(sys.argv[1]); '
            'ns["dataset_lock"](Path(sys.argv[2])).__enter__()')
    with init.dataset_lock(directory):
        result = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(SCRIPT), str(directory)],
                                capture_output=True, text=True)
        assert result.returncode != 0
        assert 'dataset is locked' in result.stderr
