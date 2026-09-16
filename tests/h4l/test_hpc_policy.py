"""Small policy/scheduler simulations only; never activate HPC or launch workers."""
from concurrent.futures import Future
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from higgsml.errors import ResearchError
from higgsml.hpc import GIB, resolve, single_writer
from higgsml.inference.likelihood import _profile_from_fit
from higgsml.inference.score_cache import RawScoreCache
from higgsml import resources


def test_single_node_memory_and_cpu_bounds():
    policy = resolve(cpus=40, memory_bytes=180 * GIB)
    assert policy['workers'] == 20
    assert policy['worker_threads'] == 1
    assert policy['score_cache_bytes'] == GIB
    assert resolve(cpus=8, memory_bytes=180 * GIB)['workers'] == 8
    assert resolve(cpus=40, memory_bytes=180 * GIB, threads=4)['workers'] == 10
    assert resolve(cpus=1, memory_bytes=16 * GIB)['workers'] == 1
    with pytest.raises(ResearchError, match='maximum 20'):
        resolve(cpus=40, memory_bytes=180 * GIB, workers=40)
    with pytest.raises(ResearchError):
        resolve(cpus=40, memory_bytes=6 * GIB)


@pytest.mark.parametrize('options', [dict(workers=0), dict(threads=0), dict(worker_gb=float('nan')),
                                   dict(cache_gb=8), dict(cache_gb=-1)])
def test_invalid_resource_estimates(options):
    with pytest.raises(ResearchError):
        resolve(cpus=40, memory_bytes=180 * GIB, **options)


def test_detect_affinity_slurm_and_nested_cgroup(monkeypatch):
    from pathlib import Path
    from higgsml import hpc
    monkeypatch.setattr(hpc.os, 'sched_getaffinity', lambda _: set(range(8)), raising=False)
    monkeypatch.setattr(hpc.sys, 'platform', 'linux')
    for key in tuple(hpc.os.environ):
        if key.startswith('SLURM_'):
            monkeypatch.delenv(key)
    monkeypatch.setenv('SLURM_JOB_ID', '123')
    monkeypatch.setenv('SLURM_NTASKS', '1')
    monkeypatch.setenv('SLURM_CPUS_PER_TASK', '40')
    monkeypatch.setenv('SLURM_MEM_PER_NODE', str(180 * 1024))
    monkeypatch.setattr(hpc, '_cgroup_dirs', lambda: [Path('/fake/job'), Path('/fake')])
    values = {'/proc/meminfo': 'MemAvailable: 188000000 kB', '/fake/cpu.max': '400000 100000',
              '/fake/job/memory.max': str(40 * GIB), '/fake/job/memory.current': str(2 * GIB)}
    monkeypatch.setattr(hpc, '_read', lambda path: values.get(str(path).replace('\\', '/'), ''))
    assert hpc.available_resources() == (4, 38 * GIB)
    monkeypatch.setenv('SLURM_NTASKS', '2')
    with pytest.raises(ResearchError, match='one coordinator'):
        hpc.available_resources()


def test_completion_scheduler_replenishes_but_bounds_reordering(monkeypatch):
    class Executor:
        def __init__(self):
            self.tasks = []
        def submit(self, function, task):
            future = Future()
            future.task = task
            self.tasks.append(future)
            return future
    executor = Executor()
    waited = []
    def complete(pending, **kwargs):
        values = sorted(pending, key=lambda future: future.task)
        # Hold task zero until the two-worker reorder buffer is full.
        chosen = values[-1] if len(waited) < 3 else values[0]
        if not waited or 0 not in waited:
            assert len(executor.tasks) <= 4
        waited.append(chosen.task)
        chosen.set_result((chosen.task ** 2, {}, .1, None))
        return {chosen}, set(pending) - {chosen}
    monkeypatch.setattr(resources, 'wait', complete)
    values = list(resources._completion_map(executor, iter(range(7)), 2))
    assert values == [i ** 2 for i in range(7)]
    assert waited[:4] == [1, 2, 3, 0]
    assert len(executor.tasks) == 7


def test_completion_scheduler_cancels_pending_on_error(monkeypatch):
    futures = []
    class Executor:
        def submit(self, function, task):
            future = Future()
            futures.append(future)
            return future
    def fail(pending, **kwargs):
        futures[0].set_exception(RuntimeError('worker failure'))
        return {futures[0]}, set(pending) - {futures[0]}
    monkeypatch.setattr(resources, 'wait', fail)
    with pytest.raises(RuntimeError, match='worker failure'):
        list(resources._completion_map(Executor(), iter(range(8)), 2))
    assert len(futures) == 2 and futures[1].cancelled()


def test_fixed_poi_cache_preserves_intervals_and_reuses_exact_points():
    calls = []
    def fixed(mu, *args, **kwargs):
        calls.append(mu)
        return None, np.array([(mu - 1.) ** 2])
    pyhf = SimpleNamespace(infer=SimpleNamespace(mle=SimpleNamespace(fixed_poi_fit=fixed)))
    uncached = [_profile_from_fit(pyhf, None, [1.], level, 1., 0., 0., 10.) for level in (.68, .95)]
    total = len(calls)
    calls.clear()
    cache = {}
    cached = [_profile_from_fit(pyhf, None, [1.], level, 1., 0., 0., 10., cache=cache) for level in (.68, .95)]
    assert cached == uncached
    assert len(calls) < total
    assert calls.count(0.) == calls.count(10.) == 1


def test_failed_and_nonfinite_fits_are_not_cached():
    cache, calls = {}, []
    def fixed(mu, *args, **kwargs):
        calls.append(mu)
        return None, np.array([float('nan')])
    pyhf = SimpleNamespace(infer=SimpleNamespace(mle=SimpleNamespace(fixed_poi_fit=fixed)))
    for level in (.68, .95):
        result = _profile_from_fit(pyhf, None, [1.], level, 1., 0., 0., 10., cache=cache)
        assert result['status'] == 'fit_failed'
    assert cache == {} and len(calls) == 2


def test_raw_score_cache_repeated_event_mapping_and_fallback():
    frame = pd.DataFrame({'event_id': ['a', 'b', 'c'], 'x': [.2, .4, .6]})
    bundles = {'model': {'model_id': 'fixed', 'model': {'weights': [1.]}}}
    calls = []
    def predict(bundle, population):
        calls.append(len(population))
        return population.x.to_numpy()
    cache = RawScoreCache(bundles, {'calibration': frame}, predict, 10000)
    draw = frame.iloc[[2, 0, 0, 1]]
    np.testing.assert_array_equal(cache.get('model', 'calibration', draw), [.6, .2, .2, .4])
    assert calls == [3]
    assert cache.get('model', 'assessment', frame) is None
    assert cache.get('model', 'calibration', pd.DataFrame({'event_id': ['unknown']})) is None
    limited = RawScoreCache(bundles, {'calibration': frame}, predict, 0)
    assert limited.get('model', 'calibration', frame) is None
    assert calls == [3]


def test_score_cache_defers_scientific_failures():
    frame = pd.DataFrame({'event_id': ['a']})
    def invalid(*args):
        raise ResearchError('original task-local failure')
    cache = RawScoreCache({'k': {'model': {}, 'model_id': 'm'}}, {'template': frame}, invalid, 10000)
    assert cache.get('k', 'template', frame) is None


def test_single_writer_rejects_competing_owner_and_releases(tmp_path):
    target = tmp_path / 'evaluation'
    with single_writer(target, allowed_root=tmp_path):
        assert not target.exists()
        with pytest.raises(ResearchError, match='Another coordinator'):
            with single_writer(target, allowed_root=tmp_path):
                pass
    with single_writer(target, allowed_root=tmp_path):
        pass
    with pytest.raises(ResearchError):
        with single_writer(tmp_path, allowed_root=tmp_path):
            pass


def test_training_dependencies_and_failure_stop_with_fake_processes(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from pathlib import Path
    from higgsml import hpc_execution as execution
    launched, published = [], set()
    monkeypatch.setattr(execution, 'settings', lambda: {'workers': 2})
    monkeypatch.setattr(execution, 'termination_signals', nullcontext)
    monkeypatch.setattr(execution.time, 'sleep', lambda _: None)
    class Process:
        def __init__(self, command, **kwargs):
            self.command = command
            launched.append(command)
            self.output = Path(command[command.index('--run-dir') + 1])
            if '--model-run' in command:
                assert Path(command[command.index('--model-run') + 1]) in published
        def poll(self):
            return 0
    monkeypatch.setattr(execution.subprocess, 'Popen', Process)
    monkeypatch.setattr(execution, 'validate_training_output', lambda path, *args, **kwargs: published.add(path))
    a, b, c = (tmp_path / name for name in ('train-a', 'train-b', 'calibrate-a'))
    steps = [('a', ['train', '--run-dir', str(a)]), ('b', ['train', '--run-dir', str(b)]),
             ('c', ['calibrate', '--model-run', str(a), '--run-dir', str(c)]),
             ('aggregate', ['templates', '--run-dir', str(tmp_path / 'templates')])]
    assert execution.training_steps(steps, project_root=tmp_path, output_root=tmp_path / 'out',
        dataset='synthetic', protocol={}) == steps[-1:]
    assert published == {a, b, c} and len(launched) == 3
    launched.clear()
    monkeypatch.setattr(Process, 'poll', lambda self: 3)
    with pytest.raises(ResearchError, match='Training task failed'):
        execution.training_steps(steps, project_root=tmp_path, output_root=tmp_path / 'out',
            dataset='synthetic', protocol={})
    assert len(launched) == 2


def test_training_output_verifies_payload_and_current_upstream(monkeypatch, tmp_path):
    from higgsml import hpc_execution as execution
    checked = []
    loaded = SimpleNamespace(manifest={'files': {'model.json': {}},
                                      'upstreams': [{'artifact_id': 'old'}]},
                             file=lambda name: checked.append(name))
    monkeypatch.setattr(execution, 'read_run', lambda *a, **k: SimpleNamespace(manifest={'artifact_id': 'new'}))
    arguments = ['calibrate', '--model-run', str(tmp_path / 'model')]
    with pytest.raises(ResearchError, match='stale --model-run'):
        execution.validate_training_output(tmp_path / 'calibration', arguments,
            dataset='synthetic', protocol={}, loaded=loaded)
    assert checked == ['model.json']
    loaded.manifest['upstreams'] = [{'artifact_id': 'new'}]
    execution.validate_training_output(tmp_path / 'calibration', arguments,
        dataset='synthetic', protocol={}, loaded=loaded)
