"""Command-line entry point for the MC-only H4l workflow."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from higgsml._transaction import RunPathError
from higgsml.errors import ResearchError


def build_parser():
    parser = argparse.ArgumentParser(prog='higgsml', description='Bound MC-only H4l analysis stages.')
    stages = parser.add_subparsers(dest='command', required=True)
    for name in ('audit','prepare','me-export','me-import','train','calibrate','templates','freeze',
                 'infer','mc-bootstrap','evidence-import','report'):
        sub = stages.add_parser(name)
        sub.add_argument('--dataset', choices=['atlas2020_4lep'], required=True)
        sub.add_argument('--protocol', required=True)
        sub.add_argument('--run-dir', required=True)
        sub.add_argument(
            '--resources',
            help='JSON resource settings: workers, worker_threads, root_max_entries, root_threads',
        )
        sub.add_argument('--diagnostic-entries-per-file', type=int,
                         help='Prepare only: profile a fixed eligible-entry count per ROOT file; publishes a terminal diagnostic run')
        sub.add_argument('--show-prepare-metrics', action='store_true',
                         help='Prepare only: print periodic, per-file, and final ROOT performance metrics')
        sub.add_argument('--show-prepare-progress', action='store_true',
                         help='Prepare only: show processed/total ROOT events and selected count')
        for flag in ('input-run','events','input-manifest','profile','model-run','template-run','gate-run',
                     'freeze-run','backend-config','export-run','results','reference','t1-validation','p0-validation','candidate-ledger'):
            sub.add_argument('--'+flag)
        sub.add_argument('--calibration-run', action='append', default=[])
        sub.add_argument('--assessment-me-run',action='append',default=[],help='Verified supplemental ME scores for the identical frozen discriminant')
        sub.add_argument('--result-run', action='append', default=[])
        sub.add_argument('--training-run', action='append', default=[])
        sub.add_argument('--evaluation-run', action='append', default=[])
        sub.add_argument('--evidence-run', action='append', default=[])
        sub.add_argument('--evidence-file')
        sub.add_argument('--evaluation-plan')
        sub.add_argument('--replicas', type=int)
        sub.add_argument('--bootstrap-seed', type=int)
        sub.add_argument('--candidate', choices=['M0c','M2','M3','M3-fixed200','M6','L1'], default='M3')
        sub.add_argument('--seed', type=int, default=42)
        sub.add_argument('--strength', type=float, default=0.)
        sub.add_argument('--groups', help='Ordered subset of A/B/C/D; empty string is the mass-only group baseline')
        sub.add_argument('--transform', choices=['raw','physical','absolute'], default='raw')
        sub.add_argument('--layer', choices=['T0','T1'], default='T0')
        sub.add_argument('--mu', type=float, default=1.)
        sub.add_argument('--toys', type=int, default=0)
        sub.add_argument('--expectation-kind', choices=['model_self','assessment'], default='model_self')
        sub.add_argument('--repeat-assessment', action='store_true', help='Repeat only the same frozen analysis within its registered budgets')
        sub.add_argument('--procedure', choices=['fixed','t2','stress'], default='fixed')
        sub.add_argument('--stress-kind', choices=['normalization','mass','score','correlation'], default='normalization')
        sub.add_argument('--stress-direction',type=int,choices=[-1,1],default=1)
        sub.add_argument('--stress-mode',choices=['omitted','modeled'],default='omitted')
        sub.add_argument('--reference-candidate')
    return parser


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    delegated = {
        "sample-efficiency": "higgsml.cli_sample_efficiency",
        "sample-efficiency-report": "higgsml.cli_sample_efficiency_report",
        "sample-efficiency-controls": "higgsml.cli_sample_efficiency_controls",
    }
    if arguments and arguments[0] in delegated:
        from importlib import import_module

        return import_module(delegated[arguments[0]]).main(arguments[1:])
    args = build_parser().parse_args(arguments)
    try:
        from higgsml.workflow import execute
        print(json.dumps(execute(args), ensure_ascii=False, allow_nan=False))
        return 0
    except (ResearchError, RunPathError) as error:
        logging.error('%s: %s', getattr(error,'status',type(error).__name__),error)
        return error.exit_code
    except Exception:
        logging.exception('Unexpected research failure')
        return 70


if __name__ == '__main__':
    raise SystemExit(main())
