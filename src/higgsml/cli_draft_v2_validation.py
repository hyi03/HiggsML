"""Independent supplemental evaluation; never launched by nominal commands."""
import argparse
import json
import logging
from pathlib import Path

from higgsml._transaction import RunPathError
from higgsml.errors import ResearchError
from higgsml.draft_v2.validation_protocol import load_protocol


def build_parser():
    parser = argparse.ArgumentParser(prog='higgsml draft-v2-validation')
    parser.add_argument('stage', choices=['register', 'bootstrap', 'model-self', 'report'])
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--run-root', required=True, type=Path)
    parser.add_argument('--protocol', required=True, type=Path)
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--continue', dest='continuation', action='store_true')
    parser.add_argument('--unit')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--access-review', type=Path)
    parser.add_argument('--no-progress', action='store_true')
    return parser


def execute(args, protocol):
    from higgsml.draft_v2 import validation_registry as registry
    from higgsml.draft_v2 import validation_execution, validation_reporting
    if args.stage in {'register', 'report'} and (args.unit or args.retry_failed):
        raise ResearchError('--unit and --retry-failed apply to bootstrap/model-self only')
    if args.plan_only:
        value = registry.plan(args.source_run, args.run_root, protocol)
        value['requested_stage'] = args.stage
        if args.unit:
            from higgsml.draft_v2.validation_protocol import units
            if args.unit not in units(args.stage):
                raise ResearchError('Unit does not belong to requested stage')
            value['requested_unit'] = args.unit
        return value
    if args.stage in {'bootstrap', 'model-self'}:
        return validation_execution.execute(args.source_run, args.run_root, protocol, args.stage,
            continuation=args.continuation, unit=args.unit, retry_failed=args.retry_failed,
            workers=args.workers, access_review=args.access_review, progress=not args.no_progress)
    method = registry.register if args.stage == 'register' else validation_reporting.report
    loaded = method(args.source_run, args.run_root, protocol, continuation=args.continuation)
    summary = loaded.read_json('summary.json') if args.stage == 'report' else {}
    return dict(execution_status=summary.get('execution_status', 'complete'),
        numerical_status=summary.get('numerical_status', 'not_evaluated'),
        path=str(loaded.path), artifact_id=loaded.manifest['artifact_id'], qualification=protocol['qualification'])


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
        logging.exception('Unexpected supplemental evaluation failure')
        return 70


if __name__ == '__main__':
    raise SystemExit(main())
