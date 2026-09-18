"""Thin CLI for the separately registered off-only analysis."""
import argparse
import json
from pathlib import Path
from higgsml.errors import ResearchError
from higgsml._transaction import RunPathError
from higgsml.protocol import load_protocol, DEFAULT_PATH


def main(argv=None):
    parser=argparse.ArgumentParser(description='Immutable registered mass-off attribution stages')
    parser.add_argument('stage',choices=['register','nominal','support-check','evaluation-spec','evaluation-plan','access-review','freeze','asimov','mc-bootstrap','model-self','assessment','t2','report'])
    parser.add_argument('--training-seed', type=int, choices=range(42,47))
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--gate', choices=['J0','J1'], default='J0')
    parser.add_argument('--purpose', choices=['pre_freeze_support','posthoc_support_diagnostic'], default='pre_freeze_support')
    for flag in ('j0-run','j1-run','specification-run','source-registration','source-nominal','historical-freeze'):
        parser.add_argument('--'+flag)
    parser.add_argument('--protocol',default=str(DEFAULT_PATH))
    parser.add_argument('--run-dir',required=True,type=Path)
    for flag in ('source-root','prepared-run','registration-run','template-run','freeze-run','result-run','t1-validation','access-review','evaluation-plan'):
        parser.add_argument('--'+flag)
    parser.add_argument('--evaluation-run',action='append',default=[])
    parser.add_argument('--mu',type=int,choices=[0,1,2],default=1)
    parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--worker-threads',type=int,default=1)
    parser.add_argument('--force',action='store_true',
                        help='Debug only: bypass source protocol consistency checks; outputs are non-authoritative')
    parser.add_argument('--no-progress',action='store_true',help='Disable internal evaluation progress bars')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]/'runs'
    try:
        p=load_protocol(args.protocol).to_dict()
        from higgsml.inference.seed_workflow_cli import dispatch
        result=dispatch(args,p,root)
        print(json.dumps(result,allow_nan=False))
        return 0 if args.plan_only or result['status']=='complete' else 3
    except (ResearchError,RunPathError) as error:
        print(json.dumps({'status':getattr(error,'status','invalid_run_path'),'reason':str(error)}))
        return error.exit_code


if __name__=='__main__': raise SystemExit(main())
