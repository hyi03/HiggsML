"""Single-node execution policy. No scientific settings belong in this module."""
from contextlib import contextmanager
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import sys

from higgsml.errors import ResearchError

ENV = 'HIGGSML_HPC_RESOURCES'
GIB = 1024 ** 3
THREAD_ENV = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
              'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')


def settings():
    value = os.environ.get(ENV)
    return _decode(value) if value is not None else None


@lru_cache(maxsize=8)
def _decode(value):
    return json.loads(value)


def add_arguments(parser):
    parser.add_argument('--HPC', action='store_true', help='Use allocated single-node CPU/memory resources.')
    parser.add_argument('--hpc-workers', type=int, help='Upper bound on concurrent HPC tasks.')
    parser.add_argument('--hpc-worker-memory-gb', type=float, default=8.,
                        help='Estimated GiB per worker, including score caches (default: 8).')
    parser.add_argument('--hpc-score-cache-gb', type=float, default=1.,
                        help='Call-local raw score cache limit per worker (default: 1 GiB).')


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ''


def _cgroup_dirs():
    """Resolve the process's cgroup and ancestors, including nested Slurm limits."""
    roots = []
    for line in _read('/proc/self/cgroup').splitlines():
        _, controllers, relative = line.split(':', 2)
        if not controllers:
            roots.append((Path('/sys/fs/cgroup'), relative))
        else:
            for controller in controllers.split(','):
                roots.append((Path('/sys/fs/cgroup') / controller, relative))
    result = {Path('/sys/fs/cgroup'), Path('/sys/fs/cgroup/cpu'), Path('/sys/fs/cgroup/memory')}
    for root, relative in roots:
        current = root / relative.lstrip('/')
        if '..' in current.parts:
            continue
        while current.is_relative_to(root):
            result.add(current)
            if current == root:
                break
            current = current.parent
    return result


def available_resources():
    cpus = [len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)]
    for key in ('SLURM_JOB_NUM_NODES', 'SLURM_NNODES', 'SLURM_NTASKS'):
        if key in os.environ and int(os.environ[key]) != 1:
            raise ResearchError('HPC requires one allocated node and one coordinator task')
    if 'SLURM_JOB_ID' in os.environ and 'SLURM_CPUS_PER_TASK' not in os.environ:
        raise ResearchError('HPC Slurm jobs require explicit --ntasks=1 --cpus-per-task=N')
    if 'SLURM_CPUS_PER_TASK' in os.environ:
        cpus.append(int(os.environ['SLURM_CPUS_PER_TASK']))
    memory = []
    for line in _read('/proc/meminfo').splitlines():
        if line.startswith('MemAvailable:'):
            memory.append(int(line.split()[1]) * 1024)
    if sys.platform == 'win32':
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ('total', 'available', 'page', 'available_page',
                                                      'virtual', 'available_virtual', 'extended')]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            memory.append(status.available)
    for directory in _cgroup_dirs():
        quota = _read(directory / 'cpu.max').split()
        if len(quota) == 2 and quota[0] != 'max':
            cpus.append(max(1, int(quota[0]) // int(quota[1])))
        quota_v1, period = _read(directory / 'cpu.cfs_quota_us'), _read(directory / 'cpu.cfs_period_us')
        if quota_v1 and period and int(quota_v1) > 0:
            cpus.append(max(1, int(quota_v1) // int(period)))
        for limit_name, used_name in (('memory.max', 'memory.current'),
                                     ('memory.limit_in_bytes', 'memory.usage_in_bytes')):
            limit, used = _read(directory / limit_name), _read(directory / used_name)
            if limit and limit != 'max':
                memory.append(max(0, int(limit) - int(used or 0)))
    cpu = min(cpus)
    for key, factor in (('SLURM_MEM_PER_NODE', 1), ('SLURM_MEM_PER_CPU', cpu)):
        if key in os.environ:
            amount = int(os.environ[key])
            if amount < 0:
                raise ResearchError(f'Invalid {key}')
            # Slurm --mem=0 means all available node memory, not a zero-byte cap.
            if amount:
                memory.append(amount * factor * 1024 ** 2)
    if cpu < 1 or not memory:
        raise ResearchError('Cannot determine positive CPU and memory allocation for HPC')
    return cpu, min(memory)


def resolve(*, cpus, memory_bytes, workers=None, threads=1, worker_gb=8., cache_gb=1.):
    if (type(threads) is not int or threads < 1 or
            workers is not None and (type(workers) is not int or workers < 1) or
            not math.isfinite(worker_gb) or worker_gb <= 0 or
            not math.isfinite(cache_gb) or cache_gb < 0 or cache_gb >= worker_gb):
        raise ResearchError('Invalid HPC resources; cache must fit inside worker memory estimate')
    usable = memory_bytes - max(4 * GIB, int(memory_bytes * .1))
    maximum = min(cpus // threads, int(usable // (worker_gb * GIB)))
    if maximum < 1 or workers is not None and workers > maximum:
        raise ResearchError(f'HPC resources cannot accommodate requested workers (maximum {max(0, maximum)})')
    return dict(workers=workers or maximum, worker_threads=threads, cpu_budget=cpus,
                memory_bytes=memory_bytes, worker_memory_bytes=int(worker_gb * GIB),
                score_cache_bytes=int(cache_gb * GIB), root_threads=min(4, cpus))


@contextmanager
def activation(args):
    """Scope environment overrides to the invocation; descendants inherit policy."""
    previous = {key: os.environ.get(key) for key in (ENV, *THREAD_ENV)}
    try:
        inherited = settings()
        if getattr(args, 'HPC', False):
            if getattr(args, 'hpc_workers', None) is not None and getattr(args, 'workers', None) is not None:
                raise ResearchError('Use either --workers or --hpc-workers, not both')
            cpus, memory = available_resources()
            requested = getattr(args, 'hpc_workers', None)
            if requested is None:
                requested = getattr(args, 'workers', None)
            threads = getattr(args, 'worker_threads', None)
            policy = resolve(cpus=cpus, memory_bytes=memory,
                             workers=requested, threads=1 if threads is None else threads,
                             worker_gb=args.hpc_worker_memory_gb, cache_gb=args.hpc_score_cache_gb)
            os.environ[ENV] = json.dumps(policy)
        else:
            policy = inherited
            if getattr(args, 'hpc_workers', None) is not None or getattr(args, 'hpc_worker_memory_gb', 8.) != 8. or getattr(args, 'hpc_score_cache_gb', 1.) != 1.:
                raise ResearchError('HPC tuning options require --HPC')
        if policy:
            from importlib.util import find_spec
            if any(find_spec(name) is None for name in ('cloudpickle', 'threadpoolctl')):
                raise ResearchError('HPC requires the .[parallel] dependencies before starting stages')
            for key in THREAD_ENV:
                os.environ[key] = str(policy['worker_threads'])
            print('HPC resources: ' + json.dumps(policy), flush=True)
        if hasattr(args, 'workers'):
            args.workers = args.workers if args.workers is not None else (policy['workers'] if policy else 1)
            args.worker_threads = args.worker_threads if args.worker_threads is not None else (policy['worker_threads'] if policy else 1)
            if policy and (args.workers < 1 or args.worker_threads < 1 or
                           args.workers > policy['workers'] or
                           args.workers * args.worker_threads > policy['cpu_budget']):
                raise ResearchError('Requested workers/threads exceed the inherited HPC allocation')
        yield policy
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def limit_threads():
    policy = settings()
    if policy:
        import torch
        from threadpoolctl import threadpool_limits
        torch.set_num_threads(policy['worker_threads'])
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        return threadpool_limits(limits=policy['worker_threads'])


@contextmanager
def single_writer(target, *, allowed_root):
    """OS-held advisory lock; the stable lock file must never be unlinked."""
    target, root = Path(target).absolute(), Path(allowed_root).resolve()
    if not target.resolve().is_relative_to(root) or target.resolve() == root:
        raise ResearchError('Lock target must be a child of runs')
    current = target
    while current != root and current.is_relative_to(root):
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ResearchError('Lock target cannot contain links')
        current = current.parent
    # Keep locks outside aggregate directories: existence is used by resume.
    directory = root / '.locks'
    if directory.is_symlink() or getattr(directory, 'is_junction', lambda: False)():
        raise ResearchError('Lock directory cannot be a link')
    directory.mkdir(parents=True, exist_ok=True)
    import hashlib
    filename = directory / (hashlib.sha256(os.path.normcase(str(target.resolve())).encode()).hexdigest() + '.lock')
    if filename.is_symlink():
        raise ResearchError('Lock file cannot be a link')
    with filename.open('a+b') as stream:
        try:
            if os.name == 'nt':
                import msvcrt
                stream.seek(0, 2)
                if stream.tell() == 0:
                    stream.write(b'0'); stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ResearchError(f'Another coordinator owns {target}') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
