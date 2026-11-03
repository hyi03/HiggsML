#!/usr/bin/env python3
"""Run draft-v2 nominal analysis and core supplement, with optional nested T2."""
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from higgsml._transaction import RunPathError
from higgsml import cli_draft_v2 as nominal
from higgsml import cli_draft_v2_validation as validation
from higgsml import cli_draft_v2_t2 as t2
from higgsml.draft_v2 import protocol as nominal_protocol
from higgsml.draft_v2 import validation_protocol, t2_protocol
from higgsml.errors import ResearchError
from higgsml.run_names import _validated_run_name


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', default='draft001')
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--dataset-receipt', type=Path)
    inputs.add_argument('--synthetic-events', type=Path)
    parser.add_argument('--nominal-access-review', type=Path)
    parser.add_argument('--validation-access-review', type=Path)
    parser.add_argument('--t2-access-review', type=Path)
    parser.add_argument('--with-t2', action='store_true', help='Include the separately registered 64,000-fit T2 study.')
    parser.add_argument('--through', choices=['freeze', 'nominal', 'validation-register', 'validation',
                                              't2-register', 't2-prepare', 't2'])
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--continue', dest='continuation', action='store_true')
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--no-progress', action='store_true')
    return parser


def schedule(args):
    through = args.through or ('t2' if args.with_t2 else 'validation')
    if through.startswith('t2') and not args.with_t2:
        raise ResearchError('T2 stages require --with-t2')
    stages = [('nominal', s) for s in ('prepare', 'train', 'freeze', 'evaluate', 'report')]
    stages += [('validation', s) for s in ('register', 'bootstrap', 'model-self', 'report')]
    if args.with_t2:
        stages += [('t2', s) for s in ('register', 'prepare', 'run', 'report')]
    stops = {'freeze': ('nominal', 'freeze'), 'nominal': ('nominal', 'report'),
             'validation-register': ('validation', 'register'), 'validation': ('validation', 'report'),
             't2-register': ('t2', 'register'), 't2-prepare': ('t2', 'prepare'), 't2': ('t2', 'report')}
    return stages[:stages.index(stops[through]) + 1]


def stage_args(args, family, stage, roots):
    return argparse.Namespace(
        stage=stage, run_root=roots[family], source_run=roots['nominal'],
        protocol={'nominal': nominal_protocol.DEFAULT_PROTOCOL,
                  'validation': validation_protocol.DEFAULT_PROTOCOL, 't2': t2_protocol.DEFAULT_PROTOCOL}[family],
        dataset_receipt=args.dataset_receipt or (None if args.synthetic_events else
            PROJECT_ROOT / 'data/raw/atlas2020_4lep/dataset_receipt.json'),
        synthetic_events=args.synthetic_events,
        access_review=getattr(args, family + '_access_review'),
        evaluation_run=None, continuation=args.continuation, retry_failed=False, unit=None,
        workers=args.workers, plan_only=args.plan_only, no_progress=args.no_progress)


def command(value, family):
    cli = {'nominal': 'draft-v2', 'validation': 'draft-v2-validation', 't2': 'draft-v2-t2'}[family]
    result = [sys.executable, '-m', 'higgsml.cli', cli, value.stage,
              '--protocol', str(value.protocol), '--run-root', str(value.run_root)]
    if family != 'nominal':
        result += ['--source-run', str(value.source_run), '--workers', str(value.workers)]
    elif value.stage == 'prepare':
        result += (['--synthetic-events', str(value.synthetic_events)] if value.synthetic_events else
                   ['--dataset-receipt', str(value.dataset_receipt)])
    if value.access_review and (family != 'nominal' or value.stage == 'evaluate'):
        result += ['--access-review', str(value.access_review)]
    if value.continuation:
        result.append('--continue')
    if value.no_progress:
        result.append('--no-progress')
    return result


def plan(args, stages, roots, protocols):
    """Inspect metadata only, including before the nominal source exists."""
    source = nominal.plan(roots['nominal'], protocols['nominal'],
                          [s for f, s in stages if f == 'nominal'])
    commands = [command(stage_args(args, f, s, roots), f) for f, s in stages]
    source['commands'] = [cmd for (family, _), cmd in zip(stages, commands) if family == 'nominal']
    extensions = {}
    for family, cli in [('validation', validation), ('t2', t2)]:
        requested = [s for f, s in stages if f == family]
        if not requested:
            continue
        if (roots['nominal'] / 'report/manifest.json').is_file():
            extensions[family] = cli.execute(stage_args(args, family, requested[-1], roots), protocols[family])
        else:
            extensions[family] = dict(identity_status='pending_nominal_report', payloads_opened=False)
    return dict(mode='plan_only', stages=[f'{f}:{s}' for f, s in stages],
                roots={k: str(v) for k, v in roots.items()}, nominal=source, extensions=extensions,
                commands=commands,
                qualification=protocols['nominal']['qualification'],
                note='Pending identities are not access clearance; existing units are not validated by this plan.')


def run(args, stages, roots, protocols):
    """Delegate all scientific checks and immutable publication to domain stages."""
    results, reports = {}, {}
    evaluation_path = None
    current = None
    try:
        import torch
        previous = torch.get_num_threads()
        try:
            torch.set_num_threads(1)
            for family, stage in stages:
                current = f'{family}:{stage}'
                if not args.no_progress:
                    print(f'{current.upper()} draft-v2 integrated workflow', file=sys.stderr, flush=True)
                value = stage_args(args, family, stage, roots)
                if family == 'nominal' and stage == 'report':
                    value.evaluation_run = evaluation_path
                cli = {'nominal': nominal, 'validation': validation, 't2': t2}[family]
                result = cli.execute(value, protocols[family])
                results[current] = result
                print(json.dumps(dict(stage=current, **result), allow_nan=False), flush=True)
                if current == 'nominal:evaluate':
                    evaluation_path = Path(result['path'])
                if stage == 'report':
                    reports[family] = result['path']
                if current == 'nominal:train' and result.get('scientific_status') == 'incomplete':
                    return 6, dict(execution_status='incomplete', stopped_at=current, reports=reports, results=results)
        finally:
            torch.set_num_threads(previous)
    except (ResearchError, RunPathError) as error:
        pending = {'nominal:evaluate': roots['nominal'] / 'freeze/access-review.pending.json',
                   'validation:bootstrap': roots['validation'] / 'register/access-review.pending.json',
                   't2:prepare': roots['t2'] / 'register/access-review.pending.json'}
        return getattr(error, 'exit_code', 3) or 6, dict(
            execution_status='blocked', stopped_at=current, error=str(error), reports=reports,
            pending_access_review=str(pending[current]) if current in pending else None,
            recovery='Preserve existing artifacts. Use --continue for validated reuse. Access receipts must be '
                     'reviewed separately; interrupted/corrupt units require the dedicated stage recovery command.')
    incomplete = any(r.get(k) == 'incomplete' for r in results.values()
                     for k in ('execution_status', 'scientific_status', 'numerical_status'))
    return (6 if incomplete else 0), dict(
        execution_status='incomplete' if any(r.get('execution_status') == 'incomplete' for r in results.values()) else 'complete',
        numerical_status=('incomplete' if incomplete else 'complete') if reports else 'not_evaluated',
        requested_through=f'{stages[-1][0]}:{stages[-1][1]}', reports=reports,
        qualification=protocols['nominal']['qualification'],
        note='Completion covers requested stages only; scientific qualification is unchanged.')


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        name = _validated_run_name(args.run_name)
        stages = schedule(args)
        roots = {family: PROJECT_ROOT / 'runs' / (prefix + name) for family, prefix in (
            ('nominal', 'h4l-draft-v2-'), ('validation', 'h4l-draft-v2-validation-'), ('t2', 'h4l-draft-v2-t2-'))}
        protocols = {'nominal': nominal_protocol.load_protocol(nominal_protocol.DEFAULT_PROTOCOL),
                     'validation': validation_protocol.load_protocol()}
        if args.with_t2:
            protocols['t2'] = t2_protocol.load_protocol()
        if args.plan_only:
            print(json.dumps(plan(args, stages, roots, protocols), allow_nan=False))
            return 0
        code, result = run(args, stages, roots, protocols)
        print(json.dumps(result, allow_nan=False), flush=True)
        return code
    except (ResearchError, RunPathError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return getattr(error, 'exit_code', 3) or 6


if __name__ == '__main__':
    raise SystemExit(main())
