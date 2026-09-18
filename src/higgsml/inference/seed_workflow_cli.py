"""Argument routing for the explicit v2/v3 workflows."""
from higgsml.errors import ResearchError


def dispatch(args, protocol, root):
    from higgsml.inference import seed_workflow, marginal_workflow
    workflow = marginal_workflow if args.evaluation_version == 'v3' else seed_workflow
    if args.force:
        raise ResearchError('within-seed evaluation requires audited compatibility; --force is unavailable')
    if args.workers < 1 or args.worker_threads < 1:
        raise ResearchError('workers and worker threads must be positive')
    if args.training_seed is not None and args.stage not in {'model-self','assessment','t2'}:
        raise ResearchError('--training-seed only applies to within-seed block evaluation')
    if args.plan_only:
        return workflow.metadata_plan(protocol,stage=args.stage,registration_path=args.registration_run,
            nominal_path=args.template_run,specification_path=args.specification_run,freeze_path=args.freeze_run,
            result_path=args.result_run,plan_path=args.evaluation_plan,prepared_path=args.prepared_run,
            j0_path=args.j0_run,j1_path=args.j1_run)
    import torch
    torch.set_num_threads(args.worker_threads)
    if args.stage == 'register':
        if not args.prepared_run or (not args.source_root and not args.source_registration):
            raise ResearchError('register needs prepared run and source root or source registration')
        return workflow.register(args.source_root,args.prepared_run,protocol,args.run_dir,root,args.t1_validation,
                                  source_registration=args.source_registration)
    if not args.registration_run:
        raise ResearchError('--registration-run required')
    if args.stage == 'nominal':
        return workflow.nominal(args.registration_run,protocol,args.run_dir,root,source_nominal=args.source_nominal)
    if not args.template_run:
        raise ResearchError('--template-run required')
    preparation=(args.registration_run,args.template_run,protocol,args.run_dir,root)
    if args.stage == 'support-check':
        return workflow.support_check(*preparation,gate=args.gate,j0_path=args.j0_run,purpose=args.purpose,
            historical_freeze=args.historical_freeze,access_review=args.access_review)
    if args.stage == 'evaluation-spec':
        if not args.j0_run or not args.j1_run:
            raise ResearchError('evaluation-spec needs --j0-run and --j1-run')
        return workflow.specification(*preparation,j0_path=args.j0_run,j1_path=args.j1_run)
    if args.stage == 'freeze':
        if not args.specification_run:
            raise ResearchError('freeze needs --specification-run')
        return workflow.freeze(*preparation,specification_path=args.specification_run)
    if args.stage == 'report':
        return workflow.report(*preparation,freeze_path=args.freeze_run,result_path=args.result_run,
            evaluation_plan_path=args.evaluation_plan,evaluation_paths=args.evaluation_run,
            j0_path=args.j0_run,j1_path=args.j1_run)
    if not args.freeze_run:
        raise ResearchError('--freeze-run required')
    common=(args.registration_run,args.template_run,args.freeze_run,protocol,args.run_dir,root)
    if args.stage == 'asimov':
        return workflow.asimov(*common)
    if not args.result_run:
        raise ResearchError('--result-run required')
    if args.stage == 'evaluation-plan':
        return workflow.evaluation_plan(args.registration_run,args.template_run,args.freeze_run,args.result_run,
                                        protocol,args.run_dir,root)
    if not args.evaluation_plan:
        raise ResearchError('--evaluation-plan required')
    if args.stage == 'access-review':
        if not args.access_review:
            raise ResearchError('--access-review source receipt required')
        return workflow.access_adapter(*common,evaluation_plan_path=args.evaluation_plan,
                                        result_path=args.result_run,access_review=args.access_review)
    return workflow.evaluate(*common,stage=args.stage,mu=args.mu,training_seed=args.training_seed,
        access_review=args.access_review,evaluation_plan_path=args.evaluation_plan,result_path=args.result_run,
        workers=args.workers,worker_threads=args.worker_threads)
