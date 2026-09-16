"""Bounded subprocess DAG execution for independent train/calibrate artifacts."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from higgsml.artifacts import read_run
from higgsml.errors import ResearchError
from higgsml.hpc import settings
from higgsml.workflow_resume import classify_stage


def validate_training_output(path, arguments, *, dataset, protocol, loaded=None):
    item = loaded or read_run(path, dataset=dataset, protocol=protocol, stages=(arguments[0],))
    for name in item.manifest['files']:
        item.file(name)
    bound = {row['artifact_id'] for row in item.manifest['upstreams']}
    for flag in ('--input-run', '--gate-run', '--model-run'):
        if flag in arguments:
            upstream = read_run(arguments[arguments.index(flag)+1], dataset=dataset, protocol=protocol)
            if upstream.manifest['artifact_id'] not in bound:
                raise ResearchError(f'Training output has stale {flag} binding: {path}')


@contextmanager
def termination_signals():
    previous = {}
    def stop(signum, frame):
        raise KeyboardInterrupt(f'Terminated by signal {signum}')
    for name in ('SIGTERM', 'SIGINT'):
        sig = getattr(signal, name)
        previous[sig] = signal.signal(sig, stop)
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def stop_process(process):
    if process.poll() is not None:
        return
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def supervised_run(command, *, cwd):
    """Forward termination to the whole CLI process group, including pool workers."""
    with termination_signals():
        process = subprocess.Popen(command, cwd=cwd, start_new_session=os.name == 'posix')
        try:
            return process.wait()
        finally:
            stop_process(process)


def training_steps(steps, *, project_root, output_root, dataset, protocol, resume=False):
    """Run the train/calibrate prefix and return ordered aggregate stages."""
    policy = settings()
    if not policy:
        return steps
    parallel = [(label, arguments) for label, arguments in steps if arguments[0] in {'train', 'calibrate'}]
    rest = [(label, arguments) for label, arguments in steps if arguments[0] not in {'train', 'calibrate'}]
    tasks = {}
    for index, (label, arguments) in enumerate(parallel):
        path = Path(arguments[arguments.index('--run-dir') + 1])
        if path in tasks:
            raise ResearchError(f'Duplicate scheduled output: {path}')
        dependencies = set()
        if arguments[0] == 'calibrate':
            dependencies.add(Path(arguments[arguments.index('--model-run') + 1]))
        tasks[path] = dict(index=index, label=label, arguments=arguments, dependencies=dependencies)
    if any(not task['dependencies'] <= set(tasks) for task in tasks.values()):
        raise ResearchError('Training schedule has an unresolved dependency')
    logs = Path(project_root) / 'runs' / '.hpc-executions' / uuid.uuid4().hex
    logs.mkdir(parents=True)
    pending, active, complete = dict(tasks), {}, set()
    record = dict(resources=policy, output_root=str(output_root), tasks=[], status='interrupted',
                  started_unix=time.time())
    failure = None
    started = time.perf_counter()
    with termination_signals():
        try:
            while pending or active:
                # Drain failures before considering any further submissions.
                for path, (process, stream, start, task) in list(active.items()):
                    code = process.poll()
                    if code is None:
                        continue
                    stream.close()
                    del active[path]
                    row = dict(label=task['label'], output=str(path), exit_code=code,
                               elapsed_seconds=time.perf_counter() - start)
                    record['tasks'].append(row)
                    if code:
                        failure = failure or ResearchError(f'Training task failed ({code}): {path}; see {logs}')
                    else:
                        try:
                            validate_training_output(path, task['arguments'], dataset=dataset, protocol=protocol)
                            complete.add(path)
                        except ResearchError as exc:
                            failure = failure or exc
                    print(f'HPC training: completed={len(complete)}/{len(tasks)} active={len(active)}', flush=True)
                if failure:
                    if active:
                        time.sleep(.1)
                        continue
                    raise failure
                ready = [(path, task) for path, task in pending.items() if task['dependencies'] <= complete]
                for path, task in ready[:max(0, policy['workers'] - len(active))]:
                    del pending[path]
                    if resume:
                        action = classify_stage(path, allowed_root=output_root, dataset=dataset,
                            protocol=protocol, stages=(task['arguments'][0],),
                            validator=lambda item, task=task, path=path: validate_training_output(
                                path, task['arguments'], dataset=dataset, protocol=protocol, loaded=item))
                        if action == 'skip':
                            complete.add(path)
                            record['tasks'].append(dict(label=task['label'], output=str(path), status='reused'))
                            continue
                    stream = (logs / f"{task['index']:04d}.log").open('x', encoding='utf-8')
                    try:
                        process = subprocess.Popen([sys.executable, '-m', 'higgsml.cli', *task['arguments']],
                            cwd=project_root, stdout=stream, stderr=subprocess.STDOUT,
                            start_new_session=os.name == 'posix')
                    except BaseException:
                        stream.close()
                        raise
                    active[path] = (process, stream, time.perf_counter(), task)
                if pending and not active and not ready:
                    raise ResearchError('Training dependency graph cannot make progress')
                if active:
                    time.sleep(.1)
            record['status'] = 'complete'
        except BaseException as exc:
            record['status'] = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed'
            record['error_type'] = type(exc).__name__
            raise
        finally:
            for process, stream, _, _ in active.values():
                stop_process(process)
                stream.close()
            record['elapsed_seconds'] = time.perf_counter() - started
            with (logs / 'execution.json').open('x', encoding='utf-8') as stream:
                json.dump(record, stream, indent=2)
    return rest
