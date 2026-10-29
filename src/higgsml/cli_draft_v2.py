"""Explicit-protocol entry point for the independent draft-v2 workflow."""
import argparse
import json
import logging
from pathlib import Path
import sys

from higgsml._transaction import RunPathError
from higgsml.errors import ResearchError
from higgsml.draft_v2.protocol import candidate_keys, load_protocol


def build_parser():
    parser = argparse.ArgumentParser(prog='higgsml draft-v2', description='Independent three-role all-MC exploratory study.')
    parser.add_argument('stage', choices=['prepare', 'train', 'freeze', 'evaluate', 'report'])
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--run-root', required=True, type=Path)
    parser.add_argument('--dataset-receipt', type=Path)
    parser.add_argument('--synthetic-events', type=Path)
    parser.add_argument('--access-review', type=Path)
    parser.add_argument('--evaluation-run', type=Path)
    parser.add_argument('--continue', dest='continuation', action='store_true')
    parser.add_argument('--retry-failed', action='store_true', help='Explicitly retry an interrupted evaluation under the identical freeze.')
    parser.add_argument('--plan-only', action='store_true', help='Read metadata only; no event files, output creation or child execution.')
    return parser


def plan(root, protocol, stages, *, protocol_path=None):
    """Read manifest metadata only; never use LoadedRun.file on an event file."""
    manifests = {}
    for name in ('prepare', 'freeze', 'evaluate', 'report'):
        path = Path(root) / name / 'manifest.json'
        if path.is_file():
            from higgsml.artifacts import read_json, digest_json
            value = read_json(path)
            if value.get('protocol_sha256') != digest_json(protocol):
                raise ResearchError('Existing stage uses another protocol')
            manifests[name] = {'artifact_id': value.get('artifact_id'), 'status': value.get('status')}
    from higgsml.artifacts import digest_json
    from higgsml.draft_v2.protocol import DEFAULT_PROTOCOL
    from higgsml.draft_v2.workflow import history
    audit = history(root, protocol, freeze_artifact_id=manifests.get('freeze', {}).get('artifact_id'))
    return dict(mode='plan_only', stages=stages, run_root=str(root), manifests=manifests,
        history=audit, history_sha256=digest_json(audit),
        commands=[[sys.executable, '-m', 'higgsml.cli', 'draft-v2', stage,
                   '--protocol', str(protocol_path or DEFAULT_PROTOCOL), '--run-root', str(root)] for stage in stages],
        prepared_identity='available_metadata_only' if 'prepare' in manifests else 'pending_prepare_identity',
        candidates=candidate_keys(), roles=protocol['roles'], source_population='all_mc',
        final_evaluation_requires=['all fifteen frozen models and validation thresholds',
                                   'explicit bound access review and durable claim'],
        qualification=protocol['qualification'])


def execute(args, protocol):
    if args.plan_only:
        return plan(args.run_root, protocol, [args.stage], protocol_path=args.protocol)
    from higgsml.draft_v2 import workflow
    if args.retry_failed and args.stage != 'evaluate':
        raise ResearchError('--retry-failed applies only to evaluation')
    kwargs = {'continuation': args.continuation}
    if args.stage == 'prepare':
        kwargs.update(receipt=args.dataset_receipt, synthetic_events=args.synthetic_events)
    elif args.stage == 'evaluate':
        kwargs.update(access_review=args.access_review, retry_failed=args.retry_failed)
    elif args.stage == 'report':
        kwargs.update(evaluation_run=args.evaluation_run)
    loaded = getattr(workflow, args.stage)(args.run_root, protocol, **kwargs)
    if isinstance(loaded, list):
        states = [r.read_json('training-state.json') for r in loaded]
        return dict(execution_status='complete', scientific_status='complete' if
                    all(s['status'] == 'trained' for s in states) else 'incomplete', training_states=states)
    summary = loaded.read_json('summary.json') if args.stage in {'evaluate', 'report'} else {}
    return dict(execution_status='complete', scientific_status=summary.get('scientific_status', 'not_evaluated'),
                artifact_id=loaded.manifest['artifact_id'], path=str(loaded.path), qualification=protocol['qualification'])


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        protocol = load_protocol(args.protocol)
        if args.plan_only:
            result = execute(args, protocol)
        else:
            import torch
            previous = torch.get_num_threads()
            try:
                torch.set_num_threads(1)
                result = execute(args, protocol)
            finally:
                torch.set_num_threads(previous)
        print(json.dumps(result, allow_nan=False))
        return 6 if result.get('scientific_status') == 'incomplete' else 0
    except (ResearchError, RunPathError) as error:
        logging.error('%s: %s', getattr(error, 'status', type(error).__name__), error)
        return error.exit_code or 6
    except Exception:
        logging.exception('Unexpected draft-v2 failure')
        return 70


if __name__ == '__main__':
    raise SystemExit(main())
