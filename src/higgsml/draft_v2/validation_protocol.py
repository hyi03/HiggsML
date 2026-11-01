"""Fixed supplemental budgets and schedule-independent random streams."""
from pathlib import Path

import numpy as np

from higgsml.artifacts import digest_json, read_json
from higgsml.errors import ResearchError
from higgsml.draft_v2.protocol import QUALIFICATION, candidate_keys

DEFAULT_PROTOCOL = Path(__file__).resolve().parents[3] / 'config/protocols/h4l_draft_v2_validation_v1.json'
MODES = ('fixed-threshold', 'refitted-threshold')
KEYS = (*candidate_keys(), 'inclusive')
EXPECTED = {
    'schema_version': 'h4l-draft-v2-validation-v1',
    'dataset': 'atlas2020_4lep',
    'source_protocol': 'h4l-draft-v2-all-mc-602020-v1',
    'bootstrap': {'replicas': 200, 'seed': 42001, 'modes': list(MODES),
                  'sampling': 'multinomial_uniform_physical_groups_within_role',
                  'paired_across_models_and_seeds': True,
                  'evaluation_draw_shared_across_modes': True},
    'toys': {'count': 500, 'seed': 42, 'injections': [0, 1, 2],
             'auxiliary_generation': 'regenerated', 'coupling': 'independent_candidates'},
    'inference': {'layer': 'T1', 'confidence_level': .68, 'mu_bounds': [0., 20.],
                  'pyhf_version': '0.7.6'},
    'rng': 'sha256-first64-pcg64-unit-index-v1',
    'percentiles': [.16, .84, .025, .975],
    'quantile_method': 'linear',
    'failure_policy': 'retain_all_no_replacement_complete_estimands_only',
    'uncertainty_scope': 'fixed_selected_checkpoints_not_retraining_or_selection_coverage',
    'protocol_scope': 'synthetic_software_defaults_not_physics_validation',
    'qualification': QUALIFICATION,
}


def load_protocol(path=DEFAULT_PROTOCOL):
    value = read_json(Path(path))
    if digest_json(value) != digest_json(EXPECTED):
        raise ResearchError('Unsupported or changed draft-v2 validation protocol')
    return value


def units(stage=None):
    result = {f'bootstrap-{i:04d}': {'stage': 'bootstrap', 'replica': i} for i in range(200)}
    result.update({f'model-self-{key.replace(":", "-")}-mu{mu}':
                   {'stage': 'model-self', 'key': key, 'mu': mu}
                   for key in KEYS for mu in (0, 1, 2)})
    return {k: v for k, v in result.items() if stage is None or v['stage'] == stage}


def stream(source_freeze, base_seed, *identity):
    """Run names, worker counts, execution order and retry paths are excluded."""
    value = {'version': EXPECTED['rng'], 'source_freeze': source_freeze,
             'base_seed': base_seed, 'identity': list(identity)}
    seal = digest_json(value)
    return np.random.Generator(np.random.PCG64(int(seal[:16], 16))), seal
