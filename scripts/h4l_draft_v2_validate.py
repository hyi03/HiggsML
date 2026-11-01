#!/usr/bin/env python3
"""Sequential supplemental stages; requires a separate bootstrap access review."""
import argparse
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from higgsml.cli_draft_v2_validation import execute
from higgsml.draft_v2.validation_protocol import DEFAULT_PROTOCOL, load_protocol, units
from higgsml.errors import ResearchError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--run-root', type=Path)
    output.add_argument('--run-name')
    parser.add_argument('--protocol', type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument('--through', choices=['register', 'bootstrap', 'model-self', 'report'], default='report')
    parser.add_argument('--continue', dest='continuation', action='store_true')
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--unit')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--access-review', type=Path)
    parser.add_argument('--no-progress', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.run_name:
            if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.run_name):
                raise ResearchError('Run name must contain letters, digits, hyphen or underscore')
            args.run_root = args.source_run.parent/('h4l-draft-v2-validation-'+args.run_name)
        protocol = load_protocol(args.protocol)
        stages = ['register', 'bootstrap', 'model-self', 'report']
        stages = stages[:stages.index(args.through)+1]
        if args.unit:
            if args.unit not in units():
                raise ResearchError('Unknown unit')
            stages = [units()[args.unit]['stage']]
        if args.plan_only:
            args.stage = stages[-1]
            result = execute(args, protocol)
            result['requested_stages'] = stages
            print(json.dumps(result, allow_nan=False))
            return 0
        for stage in stages:
            args.stage = stage
            if not args.no_progress:
                print(f'{stage.upper()} draft-v2 supplemental evaluation', file=sys.stderr, flush=True)
            result = execute(args, protocol)
            print(json.dumps(result, allow_nan=False), flush=True)
        return 6 if result.get('execution_status') == 'incomplete' else 0
    except ResearchError as error:
        logging.error('%s', error)
        return error.exit_code or 6


if __name__ == '__main__':
    raise SystemExit(main())
