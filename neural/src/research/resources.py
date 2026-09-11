"""Call-scoped, bounded process execution; workers never publish artifacts."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
from multiprocessing import get_context

from .errors import ResearchError, ResearchStateError

DEFAULTS = dict(workers=1, worker_threads=1, root_max_entries=4096)


def load_resources(path=None):
    try:
        value = {} if path is None else json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc:
        raise ResearchError('Invalid research resource configuration') from exc
    if not isinstance(value, dict) or set(value)-set(DEFAULTS):
        raise ResearchError('Unknown research resource configuration')
    result = {**DEFAULTS, **value}
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
    _function = cloudpickle.loads(payload)


def _call(task):
    return _function(task)


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
        raise ResearchStateError('Install research-parallel dependencies for worker execution',status='dependency_missing') from exc
    iterator = iter(tasks)
    pending = deque()
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context('spawn'), initializer=_initialize,
                             initargs=(cloudpickle.dumps(function),worker_threads)) as executor:
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
