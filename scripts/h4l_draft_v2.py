#!/usr/bin/env python3
"""Run the independent draft-v2 stages; no automatic access approval."""
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from higgsml._transaction import RunPathError
from higgsml.cli_draft_v2 import plan
from higgsml.draft_v2.protocol import DEFAULT_PROTOCOL, load_protocol
from higgsml.errors import ResearchError
from higgsml.run_names import _validated_run_name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--protocol', type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument('--dataset-receipt', type=Path)
    parser.add_argument('--synthetic-events', type=Path)
    parser.add_argument('--access-review', type=Path)
    parser.add_argument('--through', choices=['prepare', 'train', 'freeze', 'report'], default='report')
    parser.add_argument('--continue', dest='continuation', action='store_true')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--no-progress', action='store_true', help='Disable terminal progress bars and stage notices.')
    args = parser.parse_args(argv)
    try:
        name = _validated_run_name(args.run_name)
        protocol = load_protocol(args.protocol)
        root = PROJECT_ROOT / 'runs' / f'h4l-draft-v2-{name}'
        stages = ['prepare', 'train', 'freeze', 'evaluate', 'report']
        stages = stages[:stages.index(args.through) + 1]
        if args.plan_only:
            result = plan(root, protocol, stages, protocol_path=args.protocol)
            for command in result['commands']:
                if command[4] == 'prepare':
                    command.extend(['--synthetic-events', str(args.synthetic_events)] if args.synthetic_events else
                        ['--dataset-receipt', str(args.dataset_receipt or PROJECT_ROOT / 'data/raw/atlas2020_4lep/dataset_receipt.json')])
                if command[4] == 'evaluate' and args.access_review:
                    command.extend(['--access-review', str(args.access_review)])
                if args.continuation:
                    command.append('--continue')
                if args.no_progress:
                    command.append('--no-progress')
            print(json.dumps(result, indent=2))
            return 0
        from higgsml.draft_v2 import workflow
        import torch
        previous = torch.get_num_threads()
        try:
            torch.set_num_threads(1)
            def announce(stage):
                if not args.no_progress:
                    print(f'{stage.upper()} draft-v2: starting stage checks and execution', file=sys.stderr, flush=True)
            receipt = args.dataset_receipt
            if receipt is None and args.synthetic_events is None:
                receipt = PROJECT_ROOT / 'data/raw/atlas2020_4lep/dataset_receipt.json'
            announce('prepare')
            workflow.prepare(root, protocol, receipt=receipt, synthetic_events=args.synthetic_events,
                             continuation=args.continuation, progress=not args.no_progress)
            if args.through == 'prepare':
                return 0
            announce('train')
            trained = workflow.train(root, protocol, continuation=args.continuation, progress=not args.no_progress)
            if any(r.read_json('training-state.json')['status'] != 'trained' for r in trained):
                print(json.dumps({'execution_status': 'complete', 'scientific_status': 'incomplete'}))
                return 6
            if args.through == 'train':
                return 0
            announce('freeze')
            workflow.freeze(root, protocol, continuation=args.continuation)
            if args.through == 'freeze':
                print(f'Frozen. Review {root / "freeze/access-review.pending.json"}; pending is not approval.')
                return 0
            announce('evaluate')
            evaluation = workflow.evaluate(root, protocol, access_review=args.access_review,
                                          continuation=args.continuation, retry_failed=args.retry_failed)
            announce('report')
            report = workflow.report(root, protocol, evaluation_run=evaluation.path, continuation=args.continuation)
            summary = report.read_json('summary.json')
            print(json.dumps(dict(execution_status='complete', scientific_status=summary['scientific_status'],
                report=str(report.path), qualification=protocol['qualification'])))
            return 0 if summary['scientific_status'] == 'complete' else 6
        finally:
            torch.set_num_threads(previous)
    except (ResearchError, RunPathError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return getattr(error, 'exit_code', 3) or 6


if __name__ == '__main__':
    raise SystemExit(main())
