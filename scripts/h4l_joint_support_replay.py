"""Replay the bound development cohort; never run inference or assessment."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import torch

from higgsml.artifacts import read_json, read_run, sha256_file
from higgsml.data import load_research_data
from higgsml.errors import ResearchError
from higgsml.inference.attribution import structural_evidence
from higgsml.inference.templates import build_templates
from higgsml.modeling.discriminants import predict_discriminant
from higgsml.modeling.joint_support import analysis_contract, method_contract, select_joint_threshold

BOUND = {
    'plan.json':'873b20a08c6699092ee32f9d706d53c876345e8cec113d5670152ecc6db1ffbf',
    'summary.json':'2b4d4dbe8d043cbe20d7760d0f9a256c0ccaa31ca2a22f7e50a8e9c7e7bea84f',
    'group_draws.npz':'4ff437c280c9849ae0e04ce5fb6fa0ab0d32083ee360062cf78b9988f621741a',
    'candidate_draws.csv':'e2535049cb367f0a18ec69a8a1396b1f0daa87ebf488ff793f686a0e5a80f730',
    'provenance.json':'1d92db1c8343e346524e76e79868ec5c8de49ad901843b5118116702bc570131',
}


def _initialize(context):
    global _CONTEXT
    _CONTEXT = context
    torch.set_num_threads(1)


def _replay_candidate(item):
    roles,codes,counts,reference,bindings,protocol = _CONTEXT
    key,bundle = item
    output = []
    scores = [predict_discriminant(bundle['model'],f) for f in roles]
    for index in range(201):
        drawn, drawn_scores = [], []
        for f,s,code,draws in zip(roles,scores,codes,counts):
            m = draws[index][code]
            selected = m > 0
            part = f.loc[selected].copy()
            part['bootstrap_multiplicity'] = m[selected]
            for weight in ('physical_weight','yield_weight'):
                part[weight] *= m[selected]
            drawn.append(part)
            drawn_scores.append(s[selected])
        if bundle['candidate_id'] == 'M0off':
            # Independent copies, not m^2 moments, for baseline template validation.
            template = drawn[1].copy()
            parts = []
            for copy_index in range(int(template.bootstrap_multiplicity.max())):
                part = template.loc[template.bootstrap_multiplicity > copy_index].copy()
                part['yield_weight'] /= part.bootstrap_multiplicity
                part['event_group_id'] = part.event_group_id.astype(str)+':copy:'+str(copy_index)
                parts.append(part)
            template = pd.concat(parts,ignore_index=True).assign(category=1)
            result = build_templates(template,mass_edges=[105,140],mapping_id=bundle['mapping_id'],
                candidate_id='M0off', thresholds=protocol['templates'],
                structural_zero_evidence=structural_evidence(bundle,template,[105,140]))
            status,q,cut = result['status'],None,.5
        else:
            result = select_joint_threshold(drawn[0],drawn_scores[0],drawn[1],drawn_scores[1],protocol,
                method_contract(),dict(model_id=bundle['model_id'],mapping_id=bundle['mapping_id'],
                    candidate_key=key,seed=bundle['seed']),bindings,
                dict(stage='development_replay',cohort='nominal' if index == 0 else 'fresh',replica=index-1))
            status,q,cut = result['status'],result['selected_quantile_numerator'],result['selected_threshold']
        expected = reference.loc[(key,'nominal' if index == 0 else 'fresh',index-1)]
        if (status != 'valid' or not expected.joint_grid
                or not np.isclose(cut,expected.joint_threshold,rtol=1e-10,atol=1e-12)
                or (q is not None and not np.isclose(q/20,expected.selected_q_joint,rtol=0,atol=1e-15))):
            raise ResearchError(f'replay discrepancy {key}, row {index}, {status}, q={q}')
        output.append(dict(key=key,replica=index-1,selected_quantile_numerator=q,threshold=cut,status=status))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=Path('var/h4l-support-feasibility-20260922-001'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    if args.output.exists():
        raise ResearchError('replay output must be new')
    for name, digest in BOUND.items():
        if sha256_file(args.evidence/name) != digest:
            raise ResearchError('development evidence binding mismatch: '+name)
    for name, digest in read_json(args.evidence/'output-sha256.json').items():
        if sha256_file(args.evidence/name) != digest:
            raise ResearchError('development evidence hash mismatch: '+name)
    provenance = read_json(args.evidence/'provenance.json')
    for name, digest in provenance.items():
        if name.startswith('runs') and sha256_file(Path(name.replace('\\','/'))) != digest:
            raise ResearchError('source evidence changed: '+name)
    base = Path('runs/h4l-off-test01/source-nominal')
    protocol = read_json(base/'protocol.json')
    source = read_run(base, dataset=protocol['dataset'], protocol=protocol)
    prepared = read_run('runs/h4l-prepare/prepare', dataset=protocol['dataset'], protocol=protocol)
    frame = load_research_data(prepared.file('events.jsonl'), protocol['dataset'], protocol, allow_assessment=False)
    roles = [frame.loc[frame.role == r].reset_index(drop=True) for r in ('calibration','template')]
    del frame
    archive = np.load(args.evidence/'group_draws.npz', allow_pickle=False)
    groups = [archive[r+'_groups'] for r in ('calibration','template')]
    counts = [archive[r+'_counts'][np.r_[0,np.arange(201,401)]] for r in ('calibration','template')]
    for f, g in zip(roles, groups):
        if sorted(f.event_group_id.astype(str).unique()) != g.tolist():
            raise ResearchError('replay group ordering differs')
    codes = [pd.Index(g).get_indexer(f.event_group_id.astype(str)) for f,g in zip(roles,groups)]
    reference = pd.read_csv(args.evidence/'candidate_draws.csv')
    reference = reference[reference.cohort.isin(['nominal','fresh'])].set_index(['key','cohort','replica'])
    bindings = dict(analysis_contract_digest=analysis_contract(protocol)['analysis_contract_digest'],
        prepared_artifact_id=prepared.manifest['artifact_id'], population_id=prepared.manifest['population_id'],
        source_artifact_id=source.manifest['artifact_id'])
    torch.set_num_threads(1)
    bundles = source.read_json('calibrations.json')
    output = []
    start = time.monotonic()
    if not 1 <= args.workers <= 4:
        raise ResearchError('replay workers must be between 1 and 4')
    context = (roles,codes,counts,reference,bindings,protocol)
    with ProcessPoolExecutor(max_workers=args.workers,initializer=_initialize,initargs=(context,)) as executor:
        for number,records in enumerate(executor.map(_replay_candidate,sorted(bundles.items())),1):
            output.extend(records)
            print(f'{number}/80 candidates replayed; elapsed={time.monotonic()-start:.1f}s',flush=True)
    changed = sum(r['replica'] >= 0 and r['selected_quantile_numerator'] not in (None,10) for r in output)
    nominal = sum(r['replica'] == -1 and r['selected_quantile_numerator']==10 for r in output)
    if changed != 131 or nominal != 75:
        raise ResearchError('development replay aggregate mismatch')
    args.output.mkdir(parents=True,exist_ok=False)
    answer = dict(status='matched',evidence_level='development_replay_not_independent_validation',
        fresh_complete_support=200,planned=200,nonmedian_choices=changed,nominal_medians=nominal,
        assessment_payload_read=False,inference_run=False,bound_hashes=BOUND,
        threshold_comparison=dict(rtol=1e-10,atol=1e-12),elapsed_seconds=time.monotonic()-start)
    (args.output/'verification.json').write_text(json.dumps(answer,indent=2)+'\n',encoding='utf-8',newline='\n')
    pd.DataFrame(output).to_csv(args.output/'selections.csv',index=False,lineterminator='\n')
    print(json.dumps(answer),flush=True)


if __name__ == '__main__':
    main()
