"""Thin CLI for the separately registered off-only analysis."""
import argparse
import json
from pathlib import Path
from tqdm.auto import tqdm

from higgsml.errors import ResearchError
from higgsml._transaction import RunPathError
from higgsml.protocol import load_protocol, DEFAULT_PATH
from higgsml.inference import attribution_workflow as workflow


def main(argv=None):
    parser=argparse.ArgumentParser(description='Immutable registered mass-off attribution stages')
    parser.add_argument('stage',choices=['register','nominal','freeze','asimov','mc-bootstrap','model-self','assessment','t2','report'])
    parser.add_argument('--protocol',default=str(DEFAULT_PATH))
    parser.add_argument('--run-dir',required=True,type=Path)
    for flag in ('source-root','prepared-run','registration-run','template-run','freeze-run','result-run','t1-validation','access-review','evaluation-plan'):
        parser.add_argument('--'+flag)
    parser.add_argument('--evaluation-run',action='append',default=[])
    parser.add_argument('--mu',type=int,choices=[0,1,2],default=1)
    parser.add_argument('--worker-threads',type=int,default=1)
    parser.add_argument('--force',action='store_true',
                        help='Debug only: bypass source protocol consistency checks; outputs are non-authoritative')
    parser.add_argument('--no-progress',action='store_true',help='Disable internal evaluation progress bars')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]/'runs'
    progress_bar=None
    try:
        p=load_protocol(args.protocol).to_dict()
        if args.worker_threads<1: raise ResearchError('worker threads must be positive')
        import torch
        torch.set_num_threads(args.worker_threads)
        if args.stage=='register':
            if not args.source_root or not args.prepared_run: raise ResearchError('register needs --source-root and --prepared-run')
            result=workflow.register(args.source_root,args.prepared_run,p,args.run_dir,root,args.t1_validation,
                                     force=args.force)
        else:
            if not args.registration_run: raise ResearchError('--registration-run required')
            if args.stage!='nominal' and not args.template_run: raise ResearchError('--template-run required')
            if args.stage not in {'nominal','freeze'} and not args.freeze_run: raise ResearchError('--freeze-run required')
            if args.stage=='report' and not args.result_run: raise ResearchError('--result-run required')
            if args.stage=='nominal': result=workflow.nominal(args.registration_run,p,args.run_dir,root,force=args.force)
            elif args.stage=='freeze': result=workflow.freeze(args.registration_run,args.template_run,p,args.run_dir,root,force=args.force)
            else:
                common=(args.registration_run,args.template_run,args.freeze_run,p,args.run_dir,root)
                if args.stage=='asimov': result=workflow.asimov(*common,force=args.force)
                elif args.stage=='report': result=workflow.report(*common,result_path=args.result_run,
                                                                  evaluation_paths=args.evaluation_run,force=args.force)
                else:
                    from higgsml.inference.attribution import BUDGETS, candidate_keys
                    candidates=len(candidate_keys())
                    total=({'mc-bootstrap':BUDGETS['mc_bootstrap']['replicas']*candidates,
                            'model-self':BUDGETS['toys']['count']*candidates,
                            'assessment':BUDGETS['toys']['count']*candidates,
                            't2':BUDGETS['t2']['outer_replicas']*BUDGETS['t2']['inner_toys']*candidates}
                           [args.stage])
                    progress_bar=tqdm(total=total,desc=f'{args.stage} mu={args.mu}',unit='candidate',
                                      position=1,leave=False,disable=args.no_progress)
                    result=workflow.evaluate(*common,stage=args.stage,mu=args.mu,access_review=args.access_review,
                                             evaluation_plan_path=args.evaluation_plan,result_path=args.result_run,
                                             force=args.force,progress=progress_bar.update)
        print(json.dumps(result,allow_nan=False))
        return 0 if result['status']=='complete' else 3
    except (ResearchError,RunPathError) as error:
        print(json.dumps({'status':getattr(error,'status','invalid_run_path'),'reason':str(error)}))
        return error.exit_code
    finally:
        if progress_bar is not None:
            progress_bar.close()


if __name__=='__main__': raise SystemExit(main())
