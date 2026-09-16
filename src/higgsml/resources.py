"""Call-scoped, bounded process execution; workers never publish artifacts."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import json
from pathlib import Path
from multiprocessing import get_context

from higgsml.errors import ResearchError, ResearchStateError
from higgsml.hpc import settings
from higgsml.performance import snapshot, difference, add, peak_rss
import time

DEFAULTS = dict(workers=1, worker_threads=1, root_max_entries=4096, root_threads=4)


def load_resources(path=None):
    try:
        value = {} if path is None else json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc:
        raise ResearchError('Invalid research resource configuration') from exc
    if not isinstance(value, dict) or set(value)-set(DEFAULTS):
        raise ResearchError('Unknown research resource configuration')
    policy = settings()
    defaults = dict(DEFAULTS)
    if policy:
        defaults.update(worker_threads=policy['worker_threads'], root_threads=policy['root_threads'])
    result = {**defaults, **value}
    if any(type(v) is not int or v < 1 for v in result.values()):
        raise ResearchError('Research resources must be positive integers')
    return result


def _initialize(payload, threads):
    import cloudpickle
    from threadpoolctl import threadpool_limits
    import torch
    global _function, _thread_limit
    _thread_limit = threadpool_limits(limits=threads)
    torch.set_num_threads(threads)
    if settings() and torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    _function = cloudpickle.loads(payload)


def _call(task):
    return _function(task)


def _measured_call(task):
    before, start = snapshot(), time.perf_counter()
    result = _function(task)
    return result, difference(before), time.perf_counter() - start, peak_rss()


def _completion_map(executor, iterator, workers):
    pending, buffered = {}, {}
    submitted = emitted = completed = 0
    exhausted = False
    durations = []
    last_message = time.monotonic()
    try:
        while pending or buffered or not exhausted:
            while not exhausted and len(pending) < workers and len(pending) + len(buffered) < 2 * workers:
                try:
                    start = time.perf_counter()
                    task = next(iterator)
                    add('task_preparation_seconds', time.perf_counter() - start)
                except StopIteration:
                    exhausted = True
                    break
                pending[executor.submit(_measured_call, task)] = submitted
                submitted += 1
            if pending:
                done, _ = wait(pending, timeout=10, return_when=FIRST_COMPLETED)
                for future in done:
                    index = pending.pop(future)
                    result, metrics, duration, rss = future.result()
                    buffered[index] = result
                    durations.append(duration)
                    for key, value in metrics.items():
                        add(key, value)
                    add('worker_task_seconds', duration)
                    if rss is not None:
                        # Record maximum separately, not a sum of process RSS samples.
                        maximum = snapshot().get('worker_peak_rss_bytes', 0)
                        add('worker_peak_rss_bytes', max(0, rss - maximum))
                    completed += 1
            while emitted in buffered:
                yield buffered.pop(emitted)
                emitted += 1
            if time.monotonic() - last_message >= 10 or exhausted and not pending:
                print(f'HPC tasks: computed={completed}, ordered={emitted}, submitted={submitted}', flush=True)
                last_message = time.monotonic()
    finally:
        for future in pending:
            future.cancel()
        if durations:
            add('task_count', len(durations))
            add('task_min_seconds', min(durations))
            add('task_max_seconds', max(durations))
            for bound in (1, 10, 60, 600):
                add(f'tasks_le_{bound}_seconds', sum(value <= bound for value in durations))


def ordered_map(function, tasks, *, workers=1, worker_threads=1):
    """At most workers tasks in flight, yielding strictly in submission order."""
    if any(type(v) is not int or v < 1 for v in (workers, worker_threads)):
        raise ResearchError('Worker resources must be positive integers')
    if workers == 1:
        for task in tasks:
            yield function(task)
        return
    try:
        import cloudpickle
        import threadpoolctl
    except ImportError as exc:
        error_type = ResearchError if settings() else ResearchStateError
        raise error_type('Install .[parallel] dependencies for worker execution',status='dependency_missing') from exc
    iterator = iter(tasks)
    pending = deque()
    start = time.perf_counter()
    payload = cloudpickle.dumps(function)
    add('worker_context_serialization_seconds', time.perf_counter() - start)
    add('worker_context_bytes', len(payload))
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context('spawn'), initializer=_initialize,
                             initargs=(payload,worker_threads)) as executor:
        if settings():
            yield from _completion_map(executor, iterator, workers)
            return
        try:
            for _ in range(workers):
                try:
                    pending.append(executor.submit(_call,next(iterator)))
                except StopIteration:
                    break
            while pending:
                yield pending.popleft().result()
                try:
                    pending.append(executor.submit(_call,next(iterator)))
                except StopIteration:
                    pass
        finally:
            for future in pending:
                future.cancel()
