"""Pre-freeze marginal engineering gates; never read assessment payload."""
import math
import numpy as np
from higgsml.errors import ResearchError
from higgsml.inference.marginal_coupling import (
    canonical_seed_blocks, pairing_contract, diagnose_marginal_support)
from higgsml.inference.seed_blocks import stream_identity


def _bernoulli_group_thinning(frame, *, q, stream):
    if type(q) not in (int, float) or not math.isfinite(float(q)) or q <= 0 or q > 1:
        raise ResearchError('screening_design_unavailable')
    groups=sorted(frame.event_group_id.unique().tolist(),key=str)
    if q == 1:
        selected=set(groups); design='degenerate_q1_all_groups'
    else:
        rng=np.random.default_rng(stream['seed'])
        selected={group for group,keep in zip(groups,rng.random(len(groups)) < q) if keep}
        design='group_bernoulli_thinning'
    thinned=frame[frame.event_group_id.isin(selected)].copy()
    thinned['yield_weight']=thinned.yield_weight/q
    return thinned,{'q':q,'design':design,'groups_total':len(groups),
        'groups_selected':len(selected),'stream_id':stream['stream_id'],'stream':stream}


def _validate(inputs):
    blocks=canonical_seed_blocks()
    if set(inputs)!=set(range(42,47)) or any(inputs[b.seed]['block']!=b for b in blocks):
        raise ResearchError('v3 gates require all five canonical blocks')
    if len({tuple(v['mass_edges']) for v in inputs.values()})!=1:
        raise ResearchError('v3 gates require one common nominal grid')


def run_j0(seed_inputs):
    _validate(seed_inputs)
    results={str(seed):diagnose_marginal_support(**args) for seed,args in sorted(seed_inputs.items())}
    return {'gate':'J0','status':'passed' if all(v['summary']['qualification']=='valid' for v in results.values()) else 'failed',
            'seeds':results,'projection_tolerance':{'rtol':1e-10,'atol':1e-10}}


def run_j1(parent, *, block_inputs, q_thin, contract_digest, replicas=200, toy_base_seed=42001):
    _validate(block_inputs)
    if replicas!=200 or contract_digest!=pairing_contract()['contract_digest']:
        raise ResearchError('v3 J1 budget/contract mismatch')
    records=[]
    for replica in range(replicas):
        stream=stream_identity(contract_digest=contract_digest,stage='support-j1',mu=0,
            training_seed=42,outer_index=None,stream_kind='physical_group_thinning',
            replica_index=replica,toy_base_seed=toy_base_seed)
        sample,selection=_bernoulli_group_thinning(parent,q=q_thin,stream=stream)
        selection['q_thin']=selection.pop('q')
        summaries={}; failed={}
        for seed,args in sorted(block_inputs.items()):
            support=diagnose_marginal_support(sample,**args)
            summaries[str(seed)]=support['summary']
            if support['summary']['qualification']!='valid':
                failed[str(seed)]=support
        records.append({'replica_index':replica,'selection':selection,'seeds':summaries,'failure_diagnostics':failed})
    failures={str(s):sum(r['seeds'][str(s)]['qualification']!='valid' for r in records) for s in block_inputs}
    return {'gate':'J1','status':'passed' if not any(failures.values()) else 'failed',
        'replicas':200,'required_failures_per_seed':0,'toy_base_seed':toy_base_seed,
        'records':records,'failures_by_seed':failures,
        'seeds':{s:{'replicas':200,'support_failures':n,'qualification':'valid' if n==0 else 'insufficient_statistics'} for s,n in failures.items()}}
