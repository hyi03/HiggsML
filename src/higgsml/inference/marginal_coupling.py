"""Versioned marginal CRN contract. No empirical joint-cell intensities."""
from dataclasses import replace
import math
from collections import defaultdict
import numpy as np

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.seed_blocks import canonical_seed_blocks as joint_blocks

ROLE_MAP = {'0': 'background', '1': 'signal'}
NUMERIC = {'version': 'h4l-marginal-f64-fsum-v1', 'rtol': 1e-10, 'atol': 1e-10,
           'accumulation': 'group_first_math_fsum', 'serialization': 'canonical_json_binary64'}
METADATA = {'pairing_scope': 'within_seed', 'cross_seed_pairing': 'none',
            'pairing_kind': 'marginal_common_total_monotone_crn', 'physical_event_pairing': False,
            'uncertainty_scope': 'conditional_on_registered_crn_coupling',
            'primary_claim_eligible': False,
            'sensitivity_status': 'pending',
            'sensitivity_reason': 'Independent-allocation fit diagnostic requires a bound execution budget.'}


def pairing_contract():
    body = {'contract_id': 'h4l-mass-off-marginal-crn-v1', **METADATA,
            'seeds': list(range(42,47)), 'block_size': 16, 'candidate_family_size': 80,
            'numeric': NUMERIC, 'legacy_role_map': ROLE_MAP,
            'rng': 'sha256-full-256-PCG64-v1',
            'sensitivity': {'allocation': 'independent_category_uniform',
                            'totals': 'reuse_primary', 'toy_indexes': 'same_as_primary',
                            'summaries': ['paired_coverage', 'paired_width', 'paired_bias']}}
    return {**body, 'contract_digest': digest_json(body)}


def canonical_seed_blocks():
    digest = pairing_contract()['contract_digest']
    return tuple(replace(b, pairing_contract_digest=digest,
        block_id='seed-block:'+digest_json({'pairing_contract_digest': digest,
        'seed': b.seed, 'candidate_keys': list(b.candidate_keys)})) for b in joint_blocks())


def is_marginal(block):
    return block is not None and block.pairing_contract_digest == pairing_contract()['contract_digest']


def close(actual, reference):
    return abs(actual-reference) <= NUMERIC['atol'] + NUMERIC['rtol']*abs(reference)


def cell_stream(*, block, stage, mu, outer_index, toy_index, process, mass_bin,
                kind, toy_base_seed, candidate=None):
    body = {**({'analysis_contract_digest':block.analysis_contract_digest} if block.analysis_contract_digest else {}),
            'contract_digest': block.pairing_contract_digest, 'stage': stage, 'mu': float(mu),
            'training_seed': block.seed, 'outer_index': outer_index, 'toy_index': toy_index,
            'process': str(process), 'mass_bin': mass_bin, 'kind': kind,
            'toy_base_seed': toy_base_seed, 'candidate': candidate}
    identity = digest_json(body)
    return {**body, 'stream_id': identity, 'seed': int(identity,16)}


def diagnose_marginal_support(parent, *, block, category_columns, mass_edges,
        expected_marginals=None, role_map=None, process_column=None,
        expected_processes=None, structural_zeros=None):
    required = {'event_group_id','source_row_id','event_id','m4l','yield_weight','label', *category_columns.values()}
    if not required <= set(parent) or set(category_columns) != set(block.candidate_keys):
        raise ResearchError('marginal support identity/columns mismatch')
    if not is_marginal(block):
        raise ResearchError('marginal support requires v3 pairing contract')
    source = process_column or ('process' if 'process' in parent else 'label')
    if source not in parent or parent[source].isna().any():
        raise ResearchError('missing process identity')
    roles = dict((ROLE_MAP if source == 'label' else {}) if role_map is None else role_map)
    if source == 'label' and roles != ROLE_MAP:
        raise ResearchError('legacy role map differs from bound dataset')
    if not roles or any(type(k) is not str or v not in {'signal','background'} for k,v in roles.items()):
        raise ResearchError('missing or ambiguous bound process role map')
    processes = sorted(roles)
    if set(parent[source].astype(str)) - set(roles):
        raise ResearchError('unregistered process role')
    if not parent.label.isin([0,1]).all():
        raise ResearchError('invalid signal/background label')
    for identity, part in parent.groupby(source, sort=False):
        if set(part.label) != ({1} if roles[str(identity)] == 'signal' else {0}):
            raise ResearchError('process role/label mismatch')
    edges = np.asarray(mass_edges, dtype=np.float64)
    if edges.ndim != 1 or len(edges)<2 or not np.isfinite(edges).all() or (np.diff(edges)<=0).any():
        raise ResearchError('invalid common mass grid')
    if not np.isfinite(parent[['m4l','yield_weight']].to_numpy(float)).all():
        raise ResearchError('nonfinite marginal input')
    work = parent.copy()
    work['_p'] = work[source].astype(str)
    work['_b'] = np.searchsorted(edges, work.m4l, side='right')-1
    if ((work._b<0)|(work._b>=len(edges)-1)).any():
        raise ResearchError('parent outside half-open common mass grid')
    ids = ['event_group_id','source_row_id','event_id']
    if work[ids].isna().any().any() or work.event_id.duplicated().any():
        raise ResearchError('missing or duplicate event identity')
    for col in category_columns.values():
        if not work[col].isin([0,1]).all():
            raise ResearchError('invalid marginal category')
    if work.groupby('event_group_id')[['_p','_b',*category_columns.values()]].nunique().gt(1).any().any():
        raise ResearchError('physical group spans marginal cells')
    for col in ids:
        work[col] = work[col].astype(str)
    work = work.sort_values(['_p','_b',*ids], kind='stable')
    group_values = defaultdict(list)
    for group, weight in zip(work.event_group_id,work.yield_weight):
        group_values[group].append(float(weight))
    collapsed = work.drop_duplicates('event_group_id')
    weights = np.array([math.fsum(group_values[g]) for g in collapsed.event_group_id])
    process_values = collapsed._p.to_numpy()
    bin_values = collapsed._b.to_numpy()
    categories = {key:collapsed[col].to_numpy() for key,col in category_columns.items()}
    def total(mask):
        return math.fsum(weights[mask])
    totals, rates, cells, projection = {}, {}, [], {}
    failures = []
    maximum = 0.0
    for process in processes:
        part = process_values == process
        if total(part)<=0:
            failures.append('missing_positive_process_support')
        for b in range(len(edges)-1):
            frame = part & (bin_values==b)
            canonical = total(frame)
            totals[(process,b)] = canonical
            for key, column in category_columns.items():
                pair = [total(frame & (categories[key]==k)) for k in (0,1)]
                if any(x<0 for x in pair):
                    failures.append('negative_marginal_rate')
                error = abs(math.fsum(pair)-canonical)
                maximum = max(maximum,error)
                if not close(math.fsum(pair),canonical):
                    raise ResearchError('candidate total mismatch')
                if key.startswith('M0off:') and pair[0] != 0:
                    raise ResearchError('M0off structural zero violated')
                rates[(key,process,b)] = pair
                for k,rate in enumerate(pair):
                    projection[(key,process,b,k)] = rate
                    cells.append({'candidate_id':key,'process':process,'mass_bin':b,'category':k,
                                  'signed_sum':rate, 'zero_class':'no_events_or_structural' if rate==0 else None})
    if expected_processes is not None and set(map(str,expected_processes))-set(work._p):
        failures.append('missing_positive_process_support')
    if expected_marginals is not None:
        expected = {(c,str(p),int(b),int(k)):float(v) for (c,p,b,k),v in expected_marginals.items()}
        for key in set(expected)|set(projection):
            if not close(projection.get(key,0.), expected.get(key,0.)):
                raise ResearchError('marginal projection mismatch')
    qualification = 'physical_process' if source!='label' else 'label_level_legacy'
    summary = {'seed':block.seed,'block_id':block.block_id,
        'qualification':'insufficient_statistics' if failures else 'valid',
        'failures':sorted(set(failures)), 'identity_qualification':qualification,
        'role_map_digest':digest_json(roles), 'process_identity_source':source,
        'marginal_count':len(cells), 'positive_marginal_count':sum(c['signed_sum']>0 for c in cells),
        'minimum_rate':min((c['signed_sum'] for c in cells),default=None),
        'maximum_total_consistency_error':maximum, 'support_mismatch_count':0,
        'limitations': ['Separate background cancellation is unqualified.'] if source=='label' else []}
    support = {'summary':summary,'cells':cells,'projection':{str(k):v for k,v in projection.items()},
        'role_map':roles,'numeric_contract':NUMERIC,
        'totals':[{'process':p,'mass_bin':b,'rate':v} for (p,b),v in totals.items()],
        'marginals':[{'candidate_id':c,'process':p,'mass_bin':b,'rates':v} for (c,p,b),v in rates.items()]}
    return {**support, 'support_id':digest_json(support)}


def marginal_toys(support, *, block, mass_edges, mu, count, stage, toy_base_seed,
                  outer_index=None, independent_allocation=False):
    if (support.get('support_id') != digest_json({k:v for k,v in support.items() if k!='support_id'})
            or support['summary']['block_id'] != block.block_id):
        raise ResearchError('marginal support receipt binding mismatch')
    if support['summary']['qualification']!='valid':
        error=ResearchStateError('marginal support insufficient',status='insufficient_statistics')
        error.joint_support=support
        raise error
    if not math.isfinite(mu) or mu<0 or type(count) is not int or count<1:
        raise ResearchError('invalid marginal Toy budget/injection')
    n=len(mass_edges)-1
    obs={c:np.zeros((count,2*n),dtype=np.int64) for c in block.candidate_keys}
    rates={(r['candidate_id'],r['process'],r['mass_bin']):r['rates'] for r in support['marginals']}
    receipts=[]
    for total in support['totals']:
        p,b,base=total['process'],total['mass_bin'],total['rate']
        scaled=base*(mu if support['role_map'][p]=='signal' else 1.)
        thresholds={c: None if base==0 else rates[(c,p,b)][1]/base for c in block.candidate_keys}
        if any(t is not None and not 0<=t<=1 for t in thresholds.values()):
            raise ResearchError('marginal allocation threshold outside [0,1]')
        receipts.append({**total,'injected_rate':scaled,'theta':thresholds,
                         'zero_total':base==0, 'zero_injected_total':scaled==0})
        for toy in range(count):
            identity=dict(block=block,stage=stage,mu=mu,outer_index=outer_index,toy_index=toy,
                          process=p,mass_bin=b,toy_base_seed=toy_base_seed)
            total_stream=cell_stream(**identity,kind='physical_total_poisson')
            number=int(np.random.default_rng(total_stream['seed']).poisson(scaled))
            if number==0:
                continue
            uniforms=None
            if not independent_allocation:
                uniforms=np.sort(np.random.default_rng(cell_stream(**identity,kind='shared_category_uniform')['seed']).random(number))
            for c in block.candidate_keys:
                u=uniforms if uniforms is not None else np.sort(np.random.default_rng(cell_stream(
                    **identity,kind='independent_category_uniform',candidate=c)['seed']).random(number))
                high=int(np.searchsorted(u,thresholds[c],side='left'))
                obs[c][toy,b]=number-high+obs[c][toy,b]
                obs[c][toy,n+b]=high+obs[c][toy,n+b]
    return {'observations':{c:v.tolist() for c,v in obs.items()},
            'pairing':'marginal_common_total_independent_allocation' if independent_allocation else METADATA['pairing_kind'],
            'coupling_receipt':{'contract':pairing_contract(), 'cells':receipts,
                'support_id':support['support_id'], 'role_map':support['role_map'], 'numeric_contract':NUMERIC,
                'stage':stage,'mu':mu,'outer_index':outer_index,'toy_base_seed':toy_base_seed,
                'toy_indexes':list(range(count)), **support['summary']}}
