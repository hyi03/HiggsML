#!/usr/bin/env python3
"""Execute a sealed H4l evaluation matrix and publish one enhanced report."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from tqdm.auto import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.artifacts import digest_json  # noqa: E402
from higgsml.errors import ResearchError  # noqa: E402
from higgsml.protocol import load_protocol  # noqa: E402
from higgsml.workflow_resume import classify_stage  # noqa: E402


DEFAULT_PROTOCOL = PROJECT_ROOT / "config" / "protocols" / "h4l_protocol.json"
PLAN_SCHEMA = PROJECT_ROOT / "config" / "schemas" / "h4l_evaluation_plan_v1.schema.json"


class EvaluationError(Exception):
    def __init__(self, message, exit_code=3):
        super().__init__(message)
        self.exit_code = exit_code


def _parser():
    parser = argparse.ArgumentParser(description="Run a sealed MC bootstrap, Toy, assessment, T2, and stress evaluation matrix.")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument('--evaluation-version', choices=['v1','v2'], default='v1')
    parser.add_argument('--show-command', action='store_true')
    parser.add_argument("--prepared-run", type=Path, required=True)
    parser.add_argument("--template-run", type=Path, required=True)
    parser.add_argument("--freeze-run", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--training-run", type=Path, action="append", default=[])
    parser.add_argument("--evidence-run", type=Path, action="append", default=[])
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--registration-run", type=Path)
    parser.add_argument("--result-run", type=Path)
    parser.add_argument("--access-review", type=Path)
    parser.add_argument("--reuse-stage", action='append', default=[], metavar='STAGE:MU=RUN')
    parser.add_argument('--continue', dest='continue_run', action='store_true',
                        help='Resume an existing evaluation and skip valid complete cells.')
    parser.add_argument('--force', action='store_true',
                        help='Debug only: allow a forced-protocol off-only registration')
    parser.add_argument('--no-progress', action='store_true',
                        help='Disable stage progress bars.')
    parser.add_argument('--workers', type=int, default=1,
                        help='Process workers for evaluation stages (default: 1).')
    parser.add_argument('--worker-threads', type=int, default=1,
                        help='Threads available inside each worker (default: 1).')
    return parser


def _resolve(path):
    value = path.expanduser()
    return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()


def _display(command):
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _invoke_with_progress(command, *, label, progress):
    progress.set_postfix_str(label, refresh=True)
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    while True:
        try:
            return_code = process.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            progress.refresh()
    if return_code:
        raise EvaluationError(f'Off-only stage {label} failed; dependent stages stopped', return_code)


def _load_plan(path, protocol, plan=None):
    try:
        if plan is None: plan = json.loads(path.read_text(encoding="utf-8-sig"))
        schema = json.loads(PLAN_SCHEMA.read_text(encoding="utf-8-sig"))
        Draft202012Validator(schema).validate(plan)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise EvaluationError(f"Invalid evaluation plan: {error}") from error
    if plan["protocol_sha256"] != digest_json(protocol):
        raise EvaluationError("Evaluation plan protocol digest mismatch")
    budget = protocol["inference"]
    for section in ("model_self", "assessment"):
        if plan[section]["toys_per_injection"] > budget["toy_count"] or plan[section]["seed"] != budget["toy_seed"]:
            raise EvaluationError(f"{section} exceeds the frozen protocol budget")
    if plan["stress"]["toys"] > budget["toy_count"] or plan["stress"]["seed"] != budget["toy_seed"]:
        raise EvaluationError("stress evaluation exceeds the frozen protocol budget")
    if plan["t2"] != {"mu": 1, "seed": budget["toy_seed"],
                       "outer_replicas": budget["outer_replicas"],
                       "inner_toys": budget["inner_toys"]}:
        raise EvaluationError("T2 plan differs from the registered pilot endpoint")
    return plan


def _run(args):
    if args.workers < 1 or args.worker_threads < 1:
        raise EvaluationError('--workers and --worker-threads must be positive', 2)
    protocol_path = _resolve(args.protocol)
    protocol = load_protocol(protocol_path).to_dict()
    plan_path = _resolve(args.plan)
    from higgsml.artifacts import read_json
    from higgsml.errors import ResearchError
    try:
        plan=read_json(plan_path)
        if not isinstance(plan,dict): raise ResearchError('evaluation plan must be an object')
    except ResearchError as error:
        raise EvaluationError('Invalid evaluation plan: '+str(error)) from error
    if args.evaluation_version == 'v2':
        return _run_mass_off_v2(args,protocol,plan)
    if plan.get('schema_version') == 'h4l-mass-off-evaluation-plan-v1':
        return _run_mass_off(args, protocol, plan)
    plan = _load_plan(plan_path, protocol, plan)
    prepared, templates, freeze, output = map(_resolve, (args.prepared_run, args.template_run, args.freeze_run, args.output_root))
    try:
        relative = output.relative_to(RUNS_ROOT)
    except ValueError as error:
        raise EvaluationError("Evaluation output must be below runs", 4) from error
    if not relative.parts:
        raise EvaluationError("Evaluation output cannot be the runs root", 4)
    if not args.plan_only:
        for path in (prepared, templates, freeze):
            if not path.is_dir():
                raise EvaluationError(f"Required run does not exist: {path}")
        for name, path in (("prepared_artifact_id", prepared), ("template_artifact_id", templates),
                           ("freeze_artifact_id", freeze)):
            try:
                manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as error:
                raise EvaluationError(f"Cannot read bound input manifest: {path}") from error
            if manifest.get("artifact_id") != plan["inputs"][name]:
                raise EvaluationError(f"Evaluation plan {name} mismatch")
        if output.exists():
            raise EvaluationError(f"Evaluation output already exists: {output}", 4)
    common = ["--dataset", plan["dataset"], "--protocol", str(protocol_path)]
    steps = []
    bootstrap = output / "mc-bootstrap"
    steps.append((bootstrap, ["mc-bootstrap", *common, "--input-run", str(prepared), "--template-run", str(templates),
        "--evaluation-plan", str(plan_path), "--replicas", str(plan["mc_bootstrap"]["replicas"]),
        "--bootstrap-seed", str(plan["mc_bootstrap"]["seed"]), "--run-dir", str(bootstrap)]))
    model_self = []
    primary_model_self = None
    for mu in plan["model_self"]["injections"]:
        target = output / "model-self" / f"mu{mu}"
        model_self.append(target)
        if mu == 1:
            primary_model_self = target
        steps.append((target, ["infer", *common, "--template-run", str(templates), "--layer", "T1", "--mu", str(mu),
            "--toys", str(plan["model_self"]["toys_per_injection"]), "--seed", str(plan["model_self"]["seed"]), "--run-dir", str(target)]))
    assessment = []
    first_assessment = True
    for mu in plan["assessment"]["injections"]:
        target = output / "assessment" / f"mu{mu}"
        command = ["infer", *common, "--input-run", str(prepared), "--template-run", str(templates), "--freeze-run", str(freeze),
            "--expectation-kind", "assessment", "--layer", "T1", "--mu", str(mu),
            "--toys", str(plan["assessment"]["toys_per_injection"]), "--seed", str(plan["assessment"]["seed"]), "--run-dir", str(target)]
        if not first_assessment:
            command.append("--repeat-assessment")
        first_assessment = False
        assessment.append(target); steps.append((target, command))
    t2 = output / "t2"
    steps.append((t2, ["infer", *common, "--input-run", str(prepared), "--template-run", str(templates), "--freeze-run", str(freeze),
        "--expectation-kind", "assessment", "--procedure", "t2", "--layer", "T1", "--mu", str(plan["t2"]["mu"]),
        "--seed", str(plan["t2"]["seed"]), "--repeat-assessment", "--run-dir", str(t2)]))
    stresses = []
    for kind in plan["stress"]["kinds"]:
        for direction in plan["stress"]["directions"]:
            for mode in plan["stress"]["modes"]:
                direction_name = "minus1" if direction < 0 else "plus1"
                target = output / "stress" / f"{kind}-{direction_name}-{mode}"
                stresses.append(target)
                steps.append((target, ["infer", *common, "--input-run", str(prepared), "--template-run", str(templates),
                    "--freeze-run", str(freeze), "--expectation-kind", "assessment", "--procedure", "stress",
                    "--stress-kind", kind, "--stress-direction", str(direction), "--stress-mode", mode, "--layer", "T1",
                    "--mu", str(plan["stress"]["mu"]), "--toys", str(plan["stress"]["toys"]),
                    "--seed", str(plan["stress"]["seed"]), "--repeat-assessment", "--run-dir", str(target)]))
    report = output / "report"
    if primary_model_self is None:
        raise EvaluationError("Evaluation plan has no mu=1 model-self result")
    report_command = ["report", *common, "--result-run", str(primary_model_self),
                      "--evaluation-plan", str(plan_path), "--evaluation-run", str(templates),
                      "--evaluation-run", str(bootstrap), "--run-dir", str(report)]
    for path in [*(path for path in model_self if path != primary_model_self), *assessment, t2, *stresses]:
        report_command.extend(["--evaluation-run", str(path)])
    for path in args.training_run:
        report_command.extend(["--training-run", str(_resolve(path))])
    for path in args.evidence_run:
        report_command.extend(["--evidence-run", str(_resolve(path))])
    steps.append((report, report_command))
    for _, arguments in steps:
        command = [sys.executable, "-m", "higgsml.cli", *arguments]
        print(_display(command), flush=True)
        if not args.plan_only:
            completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
            if completed.returncode:
                raise EvaluationError(f"Evaluation stage failed with exit code {completed.returncode}", completed.returncode)
    state = "validated; input receipts deferred" if args.plan_only else "completed"
    print(f"Evaluation plan {state}: {len(steps)} stages; registration={plan['registration_status']}; plan_id={digest_json(plan)}")


def _run_mass_off(args, protocol, plan):
    from higgsml.inference.attribution import FAMILY, BUDGETS, candidate_keys
    from higgsml.artifacts import read_run, read_json
    from higgsml.errors import ResearchError
    from higgsml.inference.attribution_workflow import validate_evaluation_manifest, _load_reusable
    schema_path=PROJECT_ROOT/'config/schemas/h4l_mass_off_evaluation_plan.schema.json'
    try:
        Draft202012Validator(read_json(schema_path)).validate(plan)
    except ValidationError as error:
        raise EvaluationError('Invalid off-only plan: '+error.message) from error
    if plan['family_id']!=FAMILY or plan['candidate_keys']!=candidate_keys() or plan['budgets']!=BUDGETS or plan['protocol_sha256']!=digest_json(protocol):
        raise EvaluationError('Off-only family/protocol/budget mismatch')
    paths={'registration_artifact_id':args.registration_run,'prepared_artifact_id':args.prepared_run,
           'template_artifact_id':args.template_run,'freeze_artifact_id':args.freeze_run,'asimov_artifact_id':args.result_run}
    stages={'registration_artifact_id':'attribution-register','prepared_artifact_id':'prepare',
            'template_artifact_id':'attribution-nominal','freeze_artifact_id':'attribution-freeze','asimov_artifact_id':'attribution-asimov'}
    unresolved=[]
    loaded={}
    for key,path in paths.items():
        try:
            if path is None or plan['inputs'][key]=='0'*64: raise ResearchError('missing or placeholder identity')
            if key == 'prepared_artifact_id' and args.force:
                item,_ = _load_reusable(
                    _resolve(path),protocol,stages[key],force=True)
            else:
                item=read_run(_resolve(path),dataset=protocol['dataset'],protocol=protocol,stages=(stages[key],))
            if item.manifest['artifact_id']!=plan['inputs'][key]: raise ResearchError('manifest ID mismatch')
            loaded[key]=item
        except ResearchError as error:
            unresolved.append({'input':key,'reason':str(error)})
    if not unresolved:
        reg=plan['inputs']['registration_artifact_id']
        nominal=plan['inputs']['template_artifact_id']
        frozen=plan['inputs']['freeze_artifact_id']
        required={'template_artifact_id':{reg,plan['inputs']['prepared_artifact_id']},
                  'freeze_artifact_id':{reg,nominal},'asimov_artifact_id':{reg,nominal,frozen}}
        for key,ids in required.items():
            if not ids <= {u['artifact_id'] for u in loaded[key].manifest['upstreams']}:
                unresolved.append({'input':key,'reason':'upstream manifest binding mismatch'})
    output=_resolve(args.output_root)
    if output==RUNS_ROOT or not output.is_relative_to(RUNS_ROOT): raise EvaluationError('Output must be a fresh child of runs')
    if output.exists() and not args.continue_run: raise EvaluationError('Output already exists')
    if output.exists() and (output.is_symlink() or not output.is_dir()):
        raise EvaluationError('Output is not a reusable directory')
    if args.continue_run and args.reuse_stage and not args.plan_only:
        raise EvaluationError('--continue cannot be combined with --reuse-stage', 2)
    matrix=[('mc-bootstrap',1)]+[(stage,mu) for stage in ('model-self','assessment') for mu in (0,1,2)]+[('t2',1)]
    reused={}
    for declaration in args.reuse_stage:
        try:
            cell,path=declaration.split('=',1)
            stage,mu_text=cell.rsplit(':',1)
            cell_key=(stage,int(mu_text))
            if cell_key not in matrix or cell_key in reused: raise ValueError('unknown/duplicate cell')
            item=read_run(_resolve(Path(path)),dataset=protocol['dataset'],protocol=protocol,stages=('attribution-'+stage,))
            if validate_evaluation_manifest(item,plan)!=cell_key:
                raise ValueError('reuse artifact cohort/budget mismatch')
            if not args.plan_only: item.read_json('evaluation.json')
            reused[cell_key]=item.path
        except (ValueError,ResearchError) as error:
            raise EvaluationError('Invalid --reuse-stage: '+str(error)) from error
    print(json.dumps({'schema_version':plan['schema_version'],'family_id':FAMILY,'candidate_count':80,
                      'candidate_keys':candidate_keys(),'budgets':BUDGETS,'inputs':plan['inputs'],
                      'status':'unresolved' if unresolved else 'metadata_bound_payload_and_access_checks_pending',
                      'unresolved':unresolved,'stages':[{'stage':s,'mu':m,'output':str(output/f'{s}-mu{m}')} for s,m in matrix],
                      'completed_upstream_stages':list(loaded),'assessment_payload_opened':False,
                      'reused_stages':{f'{s}:{m}':str(path) for (s,m),path in reused.items()},
                      'registration_status':plan['registration_status'],'stress':'not_registered'},indent=2))
    if args.plan_only: return
    if unresolved: raise EvaluationError('Off-only plan has unresolved upstream identities')
    common=['--protocol',str(_resolve(args.protocol)),'--registration-run',str(_resolve(args.registration_run)),
            '--template-run',str(_resolve(args.template_run)),'--freeze-run',str(_resolve(args.freeze_run)),
            '--workers',str(args.workers),'--worker-threads',str(args.worker_threads)]
    if args.force: common.append('--force')
    if args.no_progress: common.append('--no-progress')
    outputs=[]
    with tqdm(total=len(matrix)+1, desc='H4l off evaluation', unit='stage',
              disable=args.no_progress) as progress:
        for stage,mu in matrix:
            label=f'{stage} mu={mu}'
            if (stage,mu) in reused:
                outputs.append(reused[(stage,mu)])
                progress.set_postfix_str(label+' reused',refresh=True)
                progress.update()
                continue
            target=output/f'{stage}-mu{mu}'
            if args.continue_run:
                def validate_cell(item, expected=(stage,mu)):
                    if validate_evaluation_manifest(item,plan)!=expected:
                        raise ResearchError('continued evaluation cell cohort/budget mismatch')
                    item.read_json('evaluation.json')
                try:
                    action = classify_stage(
                        target, allowed_root=output, dataset=protocol['dataset'],
                        protocol=protocol, stages=('attribution-'+stage,),
                        validator=validate_cell,
                    )
                except ResearchError as error:
                    raise EvaluationError(str(error), 4) from error
                if action == 'skip':
                    outputs.append(target)
                    progress.set_postfix_str(label+' skipped',refresh=True)
                    progress.update()
                    continue
            command=[sys.executable,'-m','higgsml.cli','attribution',stage,*common,'--mu',str(mu),'--run-dir',str(target),
                     '--evaluation-plan',str(_resolve(args.plan)),'--result-run',str(_resolve(args.result_run))]
            if stage in {'assessment','t2'} and args.access_review:
                command+=['--access-review',str(_resolve(args.access_review))]
            _invoke_with_progress(command,label=label,progress=progress)
            outputs.append(target)
            progress.update()
        report_target=output/'report'
        command=[sys.executable,'-m','higgsml.cli','attribution','report',*common,'--result-run',str(_resolve(args.result_run)),
                 '--run-dir',str(report_target)]
        for path in outputs: command+=['--evaluation-run',str(path)]
        report_action='run'
        if args.continue_run:
            try:
                report_action=classify_stage(
                    report_target, allowed_root=output, dataset=protocol['dataset'],
                    protocol=protocol, stages=('attribution-report',),
                    validator=lambda item:item.file('report.md'),
                )
            except ResearchError as error:
                raise EvaluationError(str(error),4) from error
        if report_action!='skip':
            _invoke_with_progress(command,label='final report',progress=progress)
        progress.update()


def _run_mass_off_v2(args,protocol,plan):
    from higgsml.inference import seed_workflow as workflow
    from higgsml.errors import ResearchError
    workflow.validate_plan(plan,protocol)
    if args.force or args.reuse_stage:
        raise EvaluationError('V2 reuse requires an explicit compatibility adapter; --force/--reuse-stage are unavailable')
    output=_resolve(args.output_root)
    if output==RUNS_ROOT or not output.is_relative_to(RUNS_ROOT):
        raise EvaluationError('Output must be below runs')
    if args.plan_only:
        print(json.dumps(workflow.metadata_plan(protocol,registration_path=args.registration_run,
            nominal_path=args.template_run,freeze_path=args.freeze_run,result_path=args.result_run,
            prepared_path=args.prepared_run,plan_path=args.plan),indent=2))
        return
    if output.exists() and not args.continue_run:
        raise EvaluationError('Output exists; explicit --continue required')
    if not args.registration_run or not args.result_run:
        raise EvaluationError('V2 requires --registration-run and --result-run')
    output.mkdir(parents=True,exist_ok=True)
    common=['--evaluation-version','v2','--protocol',str(_resolve(args.protocol)),
            '--registration-run',str(_resolve(args.registration_run)),
            '--template-run',str(_resolve(args.template_run)),'--freeze-run',str(_resolve(args.freeze_run)),
            '--result-run',str(_resolve(args.result_run)),'--evaluation-plan',str(_resolve(args.plan)),
            '--workers',str(args.workers),'--worker-threads',str(args.worker_threads)]
    outputs=[output/workflow.unit_name(unit) for unit in workflow.matrix()]
    failure=None
    with tqdm(total=37,desc='H4l within-seed evaluation',unit='unit',disable=args.no_progress) as progress:
        for unit in workflow.matrix():
            target=output/workflow.unit_name(unit)
            command=[sys.executable,'-m','higgsml.cli','attribution',unit['stage'],*common,
                     '--mu',str(unit['mu']),'--run-dir',str(target)]
            if unit['training_seed'] is not None: command+=['--training-seed',str(unit['training_seed'])]
            if args.access_review: command+=['--access-review',str(_resolve(args.access_review))]
            if args.show_command: print(_display(command),flush=True)
            try:
                _invoke_with_progress(command,label=workflow.unit_name(unit),progress=progress)
            except EvaluationError as error:
                failure=error
                break
            progress.update()
        report_target=output/'report'
        if report_target.exists():
            from higgsml.artifacts import sha256_file
            snapshot={}
            for path in outputs:
                snapshot[path.name]={name:sha256_file(path/name) for name in
                    ('manifest.json','seed-evaluation.json','evaluation.json') if (path/name).is_file()}
            report_target=output/('report-resume-'+digest_json(snapshot)[:16])
        if not report_target.exists():
            workflow.report(_resolve(args.registration_run),_resolve(args.template_run),protocol,report_target,RUNS_ROOT,
                freeze_path=_resolve(args.freeze_run),result_path=_resolve(args.result_run),
                evaluation_plan_path=_resolve(args.plan),evaluation_paths=outputs)
        elif workflow._load(report_target,protocol,'report').read_json('report.json')['evaluation_plan'] != plan:
            raise EvaluationError('Existing report snapshot belongs to a different evaluation plan')
        progress.update()
    print(f'Within-seed evaluation report: {report_target / "report.md"}')
    if failure: raise failure


def main():
    try:
        _run(_parser().parse_args())
    except (EvaluationError,ResearchError) as error:
        print(error, file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
