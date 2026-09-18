#!/usr/bin/env python3
"""Run the registered off-only attribution study with one command."""

from __future__ import annotations

import argparse
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

from higgsml.errors import ResearchError  # noqa: E402
from higgsml.protocol import DEFAULT_PATH, load_protocol  # noqa: E402
from higgsml.run_names import workflow_directory_name  # noqa: E402
from higgsml.workflow_resume import classify_stage  # noqa: E402


class WorkflowError(Exception):
    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Reuse one complete H4l five-seed batch and run the registered "
                     "off-only attribution workflow."),
    )
    parser.add_argument(
        "--source-run-name", required=True,
        help="Existing H4l batch name, for example 02 or T2.",
    )
    parser.add_argument(
        "--run-name", required=True,
        help="New short name; writes runs/h4l-off-<name>.",
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PATH)
    parser.add_argument(
        "--prepared-run", type=Path, default=Path("runs/h4l-prepare/prepare"),
    )
    parser.add_argument("--t1-validation", type=Path)
    parser.add_argument(
        "--access-review", type=Path,
        help=("Validated review path. Evaluation defaults to "
              "runs/h4l-off-<name>/access-review/validated-off-assessment-access.json."),
    )
    parser.add_argument(
        "--stage-b", action="store_true",
        help="Stop after the exploratory Asimov report and evaluation-plan publication.",
    )
    parser.add_argument(
        "--evaluation", action="store_true",
        help="Reuse this run name's completed Stage B and execute C-E.",
    )
    parser.add_argument("--plan", action="store_true")
    parser.add_argument(
        "--continue", dest="continue_run", action="store_true",
        help="Resume Stage B/evaluation and skip valid complete stages.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help=("Debug only: bypass source protocol consistency checks. "
              "Generated outputs are marked non-authoritative."),
    )
    parser.add_argument("--show-command", action="store_true")
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable stage progress bars.")
    parser.add_argument("--workers", type=int, default=1,
                        help="Process workers for evaluation stages (default: 1).")
    parser.add_argument("--worker-threads", type=int, default=1)
    return parser


def _resolve(path: Path) -> Path:
    value = path.expanduser()
    return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()


def _safe_run_leaf(prefix: str, name: str) -> str:
    try:
        validated = workflow_directory_name(name)
    except ValueError as error:
        raise WorkflowError(str(error), 2) from error
    return prefix + validated.removeprefix("h4l-train-")


def _display(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _invoke(command: list[str], *, show_command: bool, progress=None) -> None:
    if show_command:
        print(_display(command), flush=True)
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    while True:
        try:
            return_code = process.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if progress is not None:
                progress.refresh()
    if return_code:
        raise WorkflowError(
            f"Off-only workflow stage failed with exit code {return_code}",
            return_code,
        )


def _run(args):
    if not args.stage_b and not args.plan and args.access_review is None:
        raise WorkflowError('Full evaluation requires --access-review; use --stage-b for template-only preparation', 2)
    from higgsml.inference import marginal_workflow as workflow
    from higgsml.artifacts import read_json, read_run
    output=RUNS_ROOT / _safe_run_leaf('h4l-off-',args.run_name)
    source=RUNS_ROOT / _safe_run_leaf('h4l-train-',args.source_run_name) / 'batch' / 'all-seeds'
    protocol_path=_resolve(args.protocol)
    protocol=load_protocol(protocol_path).to_dict()
    if args.force:
        raise WorkflowError('--force cannot establish compatibility for the default marginal workflow',2)
    if args.workers < 1:
        raise WorkflowError('--workers must be positive',2)
    if args.worker_threads < 1:
        raise WorkflowError('--worker-threads must be positive',2)
    if args.stage_b and args.evaluation:
        raise WorkflowError('--stage-b cannot be combined with --evaluation',2)
    if output.exists() and not args.continue_run and not args.evaluation and not args.plan:
        raise WorkflowError('Output exists; use --continue to validate and resume',4)
    common=['--protocol',str(protocol_path),'--worker-threads',str(args.worker_threads)]
    reg=['--registration-run',str(output/'register')]
    nominal=reg+['--template-run',str(output/'nominal')]
    frozen=nominal+['--freeze-run',str(output/'freeze')]
    result=frozen+['--result-run',str(output/'asimov')]
    planned=result+['--evaluation-plan',str(output/'evaluation-plan'/'evaluation-plan.json')]
    steps=[('register',['--source-root',str(source),'--prepared-run',str(_resolve(args.prepared_run)),
                        '--t1-validation',str(_resolve(args.t1_validation or source/'templates'/'t1-validation.json'))]),
           ('nominal',reg),('support-j0',[*nominal,'--gate','J0']),
           ('support-j1',[*nominal,'--gate','J1','--j0-run',str(output/'support-j0')]),
           ('evaluation-spec',[*nominal,'--j0-run',str(output/'support-j0'),'--j1-run',str(output/'support-j1')]),
           ('freeze',[*nominal,'--specification-run',str(output/'evaluation-spec')]),
           ('asimov',frozen),('evaluation-plan',result)]
    if args.evaluation:
        steps=[]
    for name,flags in steps:
        stage='support-check' if name.startswith('support-') else name
        command=[sys.executable,'-m','higgsml.cli','attribution',stage,*common,*flags,'--run-dir',str(output/name)]
        if args.plan:
            print(_display(command)); continue
        target=output/name
        if args.continue_run and target.exists():
            read_run(target,dataset=protocol['dataset'],protocol=protocol,stages=('attribution-v3-'+name,))
        else:
            _invoke(command,show_command=args.show_command)
        if name.startswith('support-') and read_json(target/'marginal-support-summary.json')['status']!='passed':
            if (output/'gate-failure-report').exists():
                stored=workflow._load(output/'gate-failure-report',protocol,'report').read_json('report.json')
                gates=[read_json(output/gate/'marginal-support-summary.json') for gate in ('support-j0','support-j1')
                       if (output/gate).exists()]
                registered,_,_,adapter,*_=workflow.load_nominal(output/'register',output/'nominal',protocol)
                for gate in gates:
                    workflow._validate_gate(gate,registered,adapter,protocol,gate['gate'])
                if stored['support'] != gates or stored['evaluation_plan'] is not None:
                    raise WorkflowError('Existing gate report does not bind the current failed gates',4)
            else:
                workflow.report(output/'register',output/'nominal',protocol,output/'gate-failure-report',RUNS_ROOT,
                                j0_path=output/'support-j0',j1_path=output/'support-j1')
            print(f'Support qualification failed; freeze blocked. Report: {output / "gate-failure-report" / "report.md"}')
            return
    if not args.evaluation:
        command=[sys.executable,'-m','higgsml.cli','attribution','report',*common,*planned,
                 '--j0-run',str(output/'support-j0'),'--j1-run',str(output/'support-j1'),
                 '--run-dir',str(output/'report-B')]
        if args.plan: print(_display(command))
        elif not (args.continue_run and (output/'report-B').exists()): _invoke(command,show_command=args.show_command)
    if not args.stage_b:
        command=[sys.executable,str(PROJECT_ROOT/'scripts'/'h4l_evaluate.py'),
            '--plan',str(output/'evaluation-plan'/'evaluation-plan.json'),'--registration-run',str(output/'register'),
            '--prepared-run',str(_resolve(args.prepared_run)),'--template-run',str(output/'nominal'),
            '--freeze-run',str(output/'freeze'),'--result-run',str(output/'asimov'),
            '--output-root',str(output/'evaluation'),'--protocol',str(protocol_path),
            '--workers',str(args.workers),'--worker-threads',str(args.worker_threads)]
        if args.access_review: command += ['--access-review',str(_resolve(args.access_review))]
        if args.continue_run: command.append('--continue')
        if args.show_command: command.append('--show-command')
        if args.no_progress: command.append('--no-progress')
        if args.plan: print(_display(command))
        else:
            _invoke(command,show_command=args.show_command)
            # The child prints its actual immutable snapshot path; do not replace it with report/report.md.
    if args.plan:
        print('Within-seed metadata plan: 36 scientific units plus report; no payload decoded or claim consumed.')
        if not args.stage_b and args.access_review is None:
            print('Execution requires --access-review.')


def main() -> int:
    try:
        _run(_parser().parse_args())
    except (WorkflowError,ResearchError) as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
