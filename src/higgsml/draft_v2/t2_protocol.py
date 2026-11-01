"""Separately registered conditional T2 design; v1 validation stays immutable."""
from hashlib import sha256
from pathlib import Path

import numpy as np

from higgsml.artifacts import digest_json, read_json
from higgsml.errors import ResearchError
from higgsml.draft_v2.protocol import QUALIFICATION
from higgsml.draft_v2.validation_protocol import KEYS

DEFAULT_PROTOCOL = Path(__file__).resolve().parents[3]/'config/protocols/h4l_draft_v2_t2_v1.json'
EXPECTED = dict(
    schema_version='h4l-draft-v2-t2-v1', dataset='atlas2020_4lep',
    source_protocol='h4l-draft-v2-all-mc-602020-v1',
    outer=dict(count=20, seed=42002, sampling='uniform_multinomial_validation_physical_groups',
               shared_across_candidates_and_folds=True),
    inner=dict(count=100, seed=42003, injections=[1], confidence_level=.68,
               auxiliary_generation='regenerated_from_fit_template_nominal_nuisance',
               main_generation='poisson_from_other_evaluation_fold', coupling='independent_candidate_fold_toy_streams'),
    folds=dict(count=2, hash='sha256:h4l-draft-v2-t2-eval-fold-v1:group:big64:mod2',
               probability=.5, normalization='physical_weight/(0.2*0.5)',
               fixed_template_and_mother_parents=True, disjoint_physical_groups=True),
    inference=dict(layer='T1', mu_bounds=[0., 20.], pyhf_version='0.7.6'),
    threshold='validation-background-absolute-weight-empirical-median-v1',
    fixed=['networks', 'checkpoints', 'training_roles', 'evaluation_fold_membership', 'parent_events'],
    rng='sha256-first64-pcg64-t2-unit-index-v1',
    unit='candidate_x_template_fold_x_outer_replica_all_100_inner_toys',
    budget=dict(units=640, planned_fits=64000),
    failures='preserve_all_planned_inner_slots_no_replacement_or_support_rescue',
    aggregation='per_outer_then_average_two_folds_then_summarize_20_outer_clusters',
    uncertainty_scope='recalibration_conditional_on_fixed_networks_and_fixed_crossfit_parents',
    protocol_scope='synthetic_software_defaults_not_physics_validation', qualification=QUALIFICATION)


def validate_protocol(value):
    if digest_json(value) != digest_json(EXPECTED):
        raise ResearchError('Unsupported T2 protocol, parent design or budget')
    return value


def load_protocol(path=DEFAULT_PROTOCOL):
    return validate_protocol(read_json(Path(path)))


def fold_for_group(group):
    if not isinstance(group, str) or not group:
        raise ResearchError('T2 requires a physical event group identity')
    return int.from_bytes(sha256(f'h4l-draft-v2-t2-eval-fold-v1:{group}'.encode()).digest()[:8], 'big') % 2


def units():
    return {f't2-{key.replace(":", "-")}-fold{fold}-outer{outer:02d}':
            dict(key=key, template_fold=fold, mother_fold=1-fold, outer=outer, mu=1, count=100)
            for outer in range(20) for fold in range(2) for key in KEYS}


def stream(freeze_id, kind, *identity):
    base_seed = EXPECTED['outer' if kind == 'calibration' else 'inner']['seed']
    seal = digest_json(dict(version=EXPECTED['rng'], protocol_sha256=digest_json(EXPECTED),
                            source_freeze=freeze_id, base_seed=base_seed, kind=kind, identity=list(identity)))
    return np.random.Generator(np.random.PCG64(int(seal[:16], 16))), seal


def outer_draw(freeze_id, outer, group_count):
    if group_count < 1:
        raise ResearchError('T2 validation population is empty')
    rng, seal = stream(freeze_id, 'calibration', outer)
    counts = rng.multinomial(group_count, np.full(group_count, 1/group_count))
    return counts, dict(stream=seal, groups=group_count, total=int(counts.sum()),
                        multiplicity_sha256=digest_json(counts.tolist()))
