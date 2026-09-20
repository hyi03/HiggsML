#!/usr/bin/env python3
"""Execute a sealed H4l evaluation matrix and publish one enhanced report."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from tqdm.auto import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.artifacts import digest_json  # noqa: E402
from higgsml.errors import ResearchError  # noqa: E402
from higgsml.protocol import load_protocol  # noqa: E402


DEFAULT_PROTOCOL = PROJECT_ROOT / "config" / "protocols" / "h4l_protocol.json"


class EvaluationError(Exception):
    def __init__(self, message, exit_code=3):
        super().__init__(message)
        self.exit_code = exit_code


def _parser():
    parser = argparse.ArgumentParser(description="Run a sealed MC bootstrap, Toy, assessment, T2, and stress evaluation matrix.")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument('--show-command', action='store_true')
    parser.add_argument("--prepared-run", type=Path, required=True)
    parser.add_argument("--template-run", type=Path, required=True)
    parser.add_argument("--freeze-run", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--registration-run", type=Path)
    parser.add_argument("--result-run", type=Path)
    parser.add_argument("--access-review", type=Path)
    parser.add_argument("--reuse-stage", action='append', default=[], metavar='STAGE:MU=RUN')
    parser.add_argument('--continue', dest='continue_run', action='store_true',
                        help='Resume an existing evaluation and skip valid complete cells.')
    parser.add_argument('--force', action='store_true',
                        help='Debug only: allow a forced-protocol off-only registration')
    parser.add_argument('--no-progress', action='store_true',
                        help='Disable stage progress bars.')
    parser.add_argument('--workers', type=int, default=1,
                        help='Parallel workers for evaluation stages (default: 1).')
    parser.add_argument('--worker-threads', type=int, default=1,
                        help='Threads available inside each worker (default: 1).')
    return parser


def _resolve(path):
    value = path.expanduser()
    return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()


def _display(command):
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _invoke_with_progress(command, *, label, progress):
    progress.set_postfix_str(label, refresh=True)
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    while True:
        try:
            return_code = process.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            progress.refresh()
    if return_code:
        raise EvaluationError(f'Off-only stage {label} failed; dependent stages stopped', return_code)


def _run_default(args,protocol,plan):
    from higgsml.inference import marginal_workflow as workflow
    from higgsml.errors import ResearchError
    workflow.validate_plan(plan,protocol)
    if args.force or args.reuse_stage:
        raise EvaluationError('Within-seed reuse requires an explicit compatibility adapter; --force/--reuse-stage are unavailable')
    output=_resolve(args.output_root)
    if output==RUNS_ROOT or not output.is_relative_to(RUNS_ROOT):
        raise EvaluationError('Output must be below runs')
    if args.plan_only:
        print(json.dumps(workflow.metadata_plan(protocol,registration_path=args.registration_run,
            nominal_path=args.template_run,freeze_path=args.freeze_run,result_path=args.result_run,
            prepared_path=args.prepared_run,plan_path=args.plan),indent=2))
        return
    if output.exists() and not args.continue_run:
        raise EvaluationError('Output exists; explicit --continue required')
    if not args.registration_run or not args.result_run:
        raise EvaluationError('Within-seed evaluation requires --registration-run and --result-run')
    output.mkdir(parents=True,exist_ok=True)
    common=['--protocol',str(_resolve(args.protocol)),
            '--registration-run',str(_resolve(args.registration_run)),
            '--template-run',str(_resolve(args.template_run)),'--freeze-run',str(_resolve(args.freeze_run)),
            '--result-run',str(_resolve(args.result_run)),'--evaluation-plan',str(_resolve(args.plan)),
            '--workers',str(args.workers),'--worker-threads',str(args.worker_threads)]
    outputs=[output/workflow.unit_name(unit) for unit in workflow.matrix()]
    failure=None
    with tqdm(total=37,desc='H4l within-seed evaluation',unit='unit',disable=args.no_progress) as progress:
        for unit in workflow.matrix():
            target=output/workflow.unit_name(unit)
            command=[sys.executable,'-m','higgsml.cli','attribution',unit['stage'],*common,
                     '--mu',str(unit['mu']),'--run-dir',str(target)]
            if unit['training_seed'] is not None: command+=['--training-seed',str(unit['training_seed'])]
            if args.access_review: command+=['--access-review',str(_resolve(args.access_review))]
            if args.show_command: print(_display(command),flush=True)
            try:
                _invoke_with_progress(command,label=workflow.unit_name(unit),progress=progress)
            except EvaluationError as error:
                failure=error
                break
            progress.update()
        report_target=output/'report'
        if report_target.exists():
            from higgsml.artifacts import sha256_file
            snapshot={}
            for path in outputs:
                snapshot[path.name]={name:sha256_file(path/name) for name in
                    ('manifest.json','seed-evaluation.json','evaluation.json') if (path/name).is_file()}
            report_target=output/('report-resume-'+digest_json(snapshot)[:16])
        if not report_target.exists():
            workflow.report(_resolve(args.registration_run),_resolve(args.template_run),protocol,report_target,RUNS_ROOT,
                freeze_path=_resolve(args.freeze_run),result_path=_resolve(args.result_run),
                evaluation_plan_path=_resolve(args.plan),evaluation_paths=outputs)
        elif workflow._load(report_target,protocol,'report').read_json('report.json')['evaluation_plan'] != plan:
            raise EvaluationError('Existing report snapshot belongs to a different evaluation plan')
        progress.update()
    print(f'Within-seed evaluation report: {report_target / "report.md"}')
    if failure: raise failure


def _run(args):
    if args.workers < 1 or args.worker_threads < 1:
        raise EvaluationError('--workers and --worker-threads must be positive', 2)
    protocol = load_protocol(_resolve(args.protocol)).to_dict()
    from higgsml.artifacts import read_json
    try:
        plan = read_json(_resolve(args.plan))
        if not isinstance(plan, dict):
            raise ResearchError('evaluation plan must be an object')
    except ResearchError as error:
        raise EvaluationError('Invalid evaluation plan: ' + str(error)) from error
    return _run_default(args, protocol, plan)


def main():
    try:
        _run(_parser().parse_args())
    except (EvaluationError,ResearchError) as error:
        print(error, file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
