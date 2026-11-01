"""Explicit standalone crossfit T2 entry point; no automatic nominal extension."""
import argparse
import json
import logging
from pathlib import Path

from higgsml._transaction import RunPathError
from higgsml.errors import ResearchError
from higgsml.draft_v2.t2_protocol import load_protocol, units


def build_parser():
    parser = argparse.ArgumentParser(prog='higgsml draft-v2-t2')
    parser.add_argument('stage', choices=['register', 'prepare', 'run', 'report'])
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--access-review', type=Path)
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--continue', dest='continuation', action='store_true')
    parser.add_argument('--unit')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--no-progress', action='store_true')
    return parser


def execute(args, protocol):
    from higgsml.draft_v2 import t2_workflow as workflow, t2_reporting as reporting
    if args.stage in {'register', 'report'} and (args.unit or args.retry_failed):
        raise ResearchError('Unit/recovery flags apply only to prepare/run')
    if args.unit is not None and (args.unit not in units() if args.stage == 'run' else args.unit != 'preflight'):
        raise ResearchError('Unknown T2 unit for this stage')
    if args.retry_failed and args.unit is None:
        raise ResearchError('T2 recovery requires --unit and --retry-failed')
    if args.plan_only:
        return {**workflow.plan(args.source_run, args.run_root, protocol), 'requested_stage': args.stage, 'requested_unit': args.unit}
    common = dict(continuation=args.continuation)
    if args.stage == 'run':
        return workflow.execute(args.source_run, args.run_root, protocol, **common, unit=args.unit,
            retry_failed=args.retry_failed, workers=args.workers, progress=not args.no_progress, access_review=args.access_review)
    if args.stage == 'prepare':
        loaded, value = workflow.prepare(args.source_run, args.run_root, protocol, **common,
            unit=args.unit, retry_failed=args.retry_failed, access_review=args.access_review)
        numerical = 'complete' if all(c['status'] == 'valid' for c in value['cells'].values()) else 'incomplete'
        summary = dict(execution_status='complete', numerical_status=numerical)
    else:
        method = workflow.register if args.stage == 'register' else reporting.report
        loaded = method(args.source_run, args.run_root, protocol, **common)
        summary = loaded.read_json('summary.json') if args.stage == 'report' else {}
    return dict(path=str(loaded.path), artifact_id=loaded.manifest['artifact_id'],
                execution_status=summary.get('execution_status', 'complete'),
                numerical_status=summary.get('numerical_status', 'not_evaluated'), qualification=protocol['qualification'])


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = execute(args, load_protocol(args.protocol))
        print(json.dumps(result, allow_nan=False))
        return 6 if result.get('execution_status') == 'incomplete' else 0
    except (ResearchError, RunPathError) as error:
        logging.error('%s', error)
        return getattr(error, 'exit_code', 3) or 6
    except Exception:
        logging.exception('Unexpected draft-v2 T2 error')
        return 70


if __name__ == '__main__':
    raise SystemExit(main())
