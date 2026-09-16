"""Operational metrics kept separate from scientific payloads."""
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
import inspect
import json
import os
from pathlib import Path
import time
import uuid

from higgsml.hpc import settings

_counters = defaultdict(float)


def add(name, value=1):
    if settings():
        _counters[name] += value


def snapshot():
    return dict(_counters)


def difference(before):
    return {key: value - before.get(key, 0) for key, value in _counters.items()}


def peak_rss():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if os.sys.platform == 'darwin' else 1024)
    except ImportError:
        return None


@contextmanager
def timer(name):
    start = time.perf_counter()
    try:
        yield
    finally:
        add(name + '_seconds', time.perf_counter() - start)


def measured(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with timer(name):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def evaluation_metrics(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        policy = settings()
        if not policy:
            return function(*args, **kwargs)
        bound = inspect.signature(function).bind(*args, **kwargs)
        root = Path(bound.arguments['allowed_root'])
        directory = root / '.hpc-executions'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (uuid.uuid4().hex + '.json')
        record = dict(output=str(bound.arguments['output']), stage=bound.arguments.get('stage'),
                      resources=policy, status='interrupted', pid=os.getpid())
        before, start = snapshot(), time.perf_counter()
        try:
            value = function(*args, **kwargs)
            record['status'] = 'returned'
            return value
        except BaseException as exc:
            record['status'] = type(exc).__name__
            raise
        finally:
            record.update(elapsed_seconds=time.perf_counter() - start,
                          parent_peak_rss_bytes=peak_rss(), counters=difference(before))
            with path.open('x', encoding='utf-8') as stream:
                json.dump(record, stream, indent=2)
            print(f'Performance record: {path}', flush=True)
    return wrapped
