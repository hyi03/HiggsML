"""Artificial +/-10% response models, distinct from measured systematics."""
from __future__ import annotations

from copy import deepcopy
import numpy as np

from .artifacts import digest_json
from .errors import ResearchError, ResearchStateError
from .inference import build_model, require_pyhf, stress_weights
from .templates import build_templates
from .protocol import protocol_dict

STRESS_CONTRACT=dict(amplitude=.1,nuisance_bounds=[-1.,1.],auxiliary='normal',
    modifiers={'normalization':'normsys','shape':'histosys'},
    interpolation={'normsys':'code4','histosys':'code4p'},
    reference_strategy='one_frozen_reference_mapping_shared_across_methods',reference_candidate='M3:42',allowed_directions=[-1,1],
    shape_normalization='fixed_total_background_signed_yield',t1_variance='constant_relative_MC_variance')


def validate_stress_contract(protocol):
    cfg=protocol_dict(protocol).get('stress')
    if cfg != STRESS_CONTRACT:
        raise ResearchError('stress rules differ from the versioned supported contract')
    return cfg


def build_stress_templates(frame, nominal_template, *, kind, reference_mapping_id, protocol, thresholds=None):
    """Reweight a fixed template-role population without changing its mapping/grid.

    ``frame.category`` and optional ``reference_score`` must already come from
    frozen mappings. Shape responses preserve total signed background yield.
    Every endpoint retains its own event-group moments and support diagnostics.
    """
    cfg=validate_stress_contract(protocol)
    if thresholds is not None and thresholds != protocol_dict(protocol)['templates']:
        raise ResearchError('stress support thresholds differ from the frozen protocol')
    thresholds=protocol_dict(protocol)['templates']
    if not reference_mapping_id or kind not in {'normalization','mass','score','correlation'}:
        raise ResearchError('invalid artificial stress source')
    if frame.empty or set(frame.role) != {'template'}:
        raise ResearchError('stress response fitting requires template role only')
    if nominal_template.get('status') != 'valid':
        raise ResearchStateError('nominal stress template is not usable',status='insufficient_statistics')
    args=dict(mass_edges=nominal_template['mass_edges'],mapping_id=nominal_template['mapping_id'],
              candidate_id=nominal_template['candidate_id'],categories=nominal_template['categories'],
              thresholds=thresholds,structural_zero_evidence=nominal_template.get('structural_zero_evidence'))
    rebuilt=build_templates(frame,**args)
    # Bind the actual source and category assignment to the frozen nominal rates.
    for key in ('dataset','active_bins','samples'):
        if rebuilt[key] != nominal_template[key]:
            raise ResearchError('stress template source does not reproduce frozen nominal moments')
    endpoints={}
    for direction,name in ((-1,'down'),(1,'up')):
        varied=frame.copy()
        varied['yield_weight']=stress_weights(varied,kind=kind,direction=direction,reference_mapping_id=reference_mapping_id)
        artifact=build_templates(varied,**args)
        if artifact['status'] != 'valid' or artifact['active_bins'] != nominal_template['active_bins']:
            raise ResearchStateError('stress endpoint fails frozen support; no adaptive merging',status='insufficient_statistics')
        endpoints[name]=artifact
    result=dict(schema_version='research-artificial-stress-v1',status='valid',kind=kind,
        reference_mapping_id=reference_mapping_id,nominal_template_id=digest_json(nominal_template),
        source='artificial_pressure_not_physics_systematic',magnitude=cfg['amplitude'],stress_contract=deepcopy(cfg),
        normalization='background_yield_changes' if kind=='normalization' else 'fixed_total_background_signed_yield',
        mapping_id=nominal_template['mapping_id'],**endpoints)
    result['stress_id']=digest_json(result)
    return result


def build_stress_model(template, responses, *, protocol,layer='T0',t1_validation=None,mu_max=20.):
    """Add one shared normal-constrained normsys/histosys parameter.

    T1 keeps the nominal shapesys constraints and therefore requires endpoint
    relative MC variances to match nominal. Otherwise an alpha-dependent MC
    covariance contract is needed and the run stops explicitly.
    """
    cfg=validate_stress_contract(protocol)
    if (responses.get('stress_id') != digest_json({k:v for k,v in responses.items() if k!='stress_id'})
            or responses.get('nominal_template_id') != digest_json(template)
            or responses.get('mapping_id') != template.get('mapping_id') or responses.get('stress_contract')!=cfg):
        raise ResearchError('stress response/nominal binding mismatch')
    if responses.get('status') != 'valid':
        raise ResearchStateError('invalid stress response',status='insufficient_statistics')
    _,metadata=build_model(template,layer=layer,t1_validation=t1_validation,mu_max=mu_max)
    spec=deepcopy(metadata['model_spec'])
    active=template['active_bins']
    name='artificial_'+responses['kind']+'_'+responses['reference_mapping_id'][:16]
    kind=cfg['modifiers']['normalization' if responses['kind']=='normalization' else 'shape']
    endpoints={key:{s['name']:s for s in responses[key]['samples']} for key in ('down','up')}
    for original,sample in zip(template['samples'],spec['channels'][0]['samples']):
        nominal=np.asarray(original['yield'],float)[active]
        for endpoint in endpoints.values():
            varied=endpoint[original['name']]
            rates=np.asarray(varied['yield'],float)[active]
            cov=np.asarray(varied['covariance'],float)[np.ix_(active,active)]
            if not np.allclose(cov,np.diag(np.diag(cov)),rtol=0,atol=1e-12):
                raise ResearchStateError('stress endpoint group covariance unsupported',status='template_stat_model_unvalidated')
            if layer=='T1':
                var=np.asarray(original['variance'],float)[active]
                varied_var=np.asarray(varied['variance'],float)[active]
                occupied=nominal>0
                if not np.allclose(varied_var[occupied]/rates[occupied]**2,var[occupied]/nominal[occupied]**2,rtol=1e-10,atol=1e-12):
                    raise ResearchStateError('stress changes relative MC variance; alpha-dependent shapesys is unvalidated',status='template_stat_model_unvalidated')
        if original['is_signal']:
            continue
        data=({'lo':1-cfg['amplitude'],'hi':1+cfg['amplitude']} if kind=='normsys' else
              {'lo_data':np.asarray(endpoints['down'][original['name']]['yield'])[active].tolist(),
               'hi_data':np.asarray(endpoints['up'][original['name']]['yield'])[active].tolist()})
        sample['modifiers'].append(dict(name=name,type=kind,data=data))
    pyhf=require_pyhf()
    # Only endpoint stresses are generated; constrain interpolation to the
    # registered [-1,+1] range instead of extrapolating unknown responses.
    spec['parameters'].append(dict(name=name,inits=[0.],bounds=[cfg['nuisance_bounds']]))
    model=pyhf.Model(spec,poi_name='mu',modifier_settings={key:{'interpcode':value} for key,value in cfg['interpolation'].items()})
    return model,{**metadata,'model_spec':spec,'stress_id':responses['stress_id'],
        'stress_kind':responses['kind'],'stress_nuisance':name,'stress_modifier':kind,
        'stress_reference_mapping_id':responses['reference_mapping_id'],
        'stress_source':'artificial_pressure_not_physics_systematic',
        'auxiliary_constraint':'normal_artificial_stress'+('_and_poisson_tau_gamma' if layer=='T1' else ''),
        'stress_nuisance_bounds':cfg['nuisance_bounds'],'stress_contract':deepcopy(cfg),
        'template_variance_contract':'constant_relative_MC_variance' if layer=='T1' else 'T0_endpoint_moments_recorded_no_MC_nuisance'}


def sample_auxiliary(model, parameters, rng, *, policy='regenerated',shared_normals=None):
    """Generate each actual pyhf auxiliary distribution, including signed normals.

    ``shared_normals`` maps parameter names to common standard-normal deviates,
    allowing the same artificial measurement to be paired across candidates.
    """
    if policy not in {'fixed','regenerated'}:
        raise ResearchError('unknown auxiliary-generation policy')
    if model.config.nauxdata==0:
        return np.empty(0,dtype=float)
    expected=np.asarray(model.expected_auxdata(parameters),float)
    if not np.isfinite(expected).all():
        raise ResearchError('nonfinite expected auxiliary observations')
    output=expected.copy()
    offset=0
    for name in model.config.auxdata_order:
        parameter=model.config.param_set(name)
        n=parameter.n_parameters
        means=expected[offset:offset+n]
        if parameter.pdf_type=='poisson':
            if (means<0).any():
                raise ResearchError('negative Poisson auxiliary intensity')
            if policy=='regenerated':
                output[offset:offset+n]=rng.poisson(means)
        elif parameter.pdf_type=='normal':
            sigma=np.asarray(parameter.width(),float)
            if sigma.shape != (n,) or not np.isfinite(sigma).all() or (sigma<=0).any():
                raise ResearchError('invalid normal auxiliary width')
            if policy=='regenerated':
                z=(np.asarray(shared_normals[name],float) if shared_normals is not None and name in shared_normals
                   else rng.normal(size=n))
                if z.shape != (n,) or not np.isfinite(z).all():
                    raise ResearchError('shared auxiliary deviate shape invalid')
                output[offset:offset+n]=means+sigma*z
        else:
            raise ResearchStateError('unsupported auxiliary distribution',status='stress_model_unvalidated')
        offset+=n
    if offset != len(output):
        raise ResearchError('auxiliary parameter ordering mismatch')
    return output
