"""Call-scoped, bounded process execution; workers never publish artifacts."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json
from pathlib import Path
from multiprocessing import get_context

from higgsml.errors import ResearchError, ResearchStateError

DEFAULTS = dict(workers=1, worker_threads=1, root_max_entries=4096, root_threads=4)


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


def _ordered_futures(executor, submit, tasks, workers):
    iterator = iter(tasks)
    pending = deque()
    try:
        for _ in range(workers):
            try:
                pending.append(submit(executor, next(iterator)))
            except StopIteration:
                break
        while pending:
            yield pending.popleft().result()
            try:
                pending.append(submit(executor, next(iterator)))
            except StopIteration:
                pass
    finally:
        for future in pending:
            future.cancel()


def ordered_map(function, tasks, *, workers=1, worker_threads=1, execution="process"):
    """At most workers tasks in flight, yielding strictly in submission order."""
    if any(type(v) is not int or v < 1 for v in (workers, worker_threads)):
        raise ResearchError('Worker resources must be positive integers')
    if execution not in {"process", "thread"}:
        raise ResearchError('Worker execution must be process or thread')
    if workers == 1:
        for task in tasks:
            yield function(task)
        return
    try:
        import cloudpickle
        import threadpoolctl
    except ImportError as exc:
        raise ResearchStateError('Install research-parallel dependencies for worker execution',status='dependency_missing') from exc
    if execution == "thread":
        import torch
        previous_threads = torch.get_num_threads()
        try:
            torch.set_num_threads(worker_threads)
            with threadpoolctl.threadpool_limits(limits=worker_threads):
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    yield from _ordered_futures(
                        executor, lambda pool, task: pool.submit(function, task), tasks, workers)
        finally:
            torch.set_num_threads(previous_threads)
        return
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context('spawn'), initializer=_initialize,
                             initargs=(cloudpickle.dumps(function),worker_threads)) as executor:
        yield from _ordered_futures(
            executor, lambda pool, task: pool.submit(_call, task), tasks, workers)
