"""Strict versioned draft-v2 contract, independent of the five-role protocol."""
from pathlib import Path

from higgsml.artifacts import digest_json, read_json
from higgsml.errors import ResearchError

DEFAULT_PROTOCOL = Path(__file__).resolve().parents[3] / "config/protocols/h4l_draft_v2.json"
CANDIDATES = ("ABCD", "BCD", "ACD", "ABD", "ABC")
SEEDS = (42, 43, 44)
ROLES = ("train", "validation", "evaluation")
QUALIFICATION = dict(status="exploratory_posthoc", independent=False,
                     selection_aware_coverage="unvalidated", primary_claim_eligible=False)


def validate_protocol(value):
    # This version deliberately has no configurable scientific choices. A new
    # allocation/schedule requires a separately reviewed version and validator.
    expected = {
        "schema_version": "h4l-draft-v2-protocol-v1",
        "protocol_id": "h4l-draft-v2-all-mc-602020-v1", "dataset": "atlas2020_4lep",
        "source_population": "all_mc", "final_state": "2e2mu",
        "mass_window": [105., 140.], "luminosity_pb": 10000., "development_probability": 1.,
        "roles": dict(train=.6, validation=.2, evaluation=.2),
        "role_hash": "sha256:h4l-draft-v2-role-v1:group:big64:mod100",
        "candidates": list(CANDIDATES), "seeds": list(SEEDS), "mass_input": "off",
        "training": dict(max_epochs=200, patience=20, minimum_improvement=.0001,
                         batch_size=1024, learning_rate=.001, weight_decay=.0001),
        "threshold": "validation-background-absolute-weight-empirical-median-v1",
        "templates": dict(mass_edges=[105., 140.], score_categories=2, min_neff_signed=20., min_rho=.2),
        "inference": dict(pyhf_version="0.7.6", layer="T1", mu=1., mu_bounds=[0., 20.],
                          confidence_level=.68, template_modifier="shapesys",
                          template_correlation="independent_process_bins"),
        "spectra": dict(candidates=["ABCD", "BCD"], seed=42,
                        mass_edges=[105., 110., 115., 120., 125., 130., 135., 140.]),
        "protocol_scope": "synthetic_software_defaults_not_physics_validation",
        "qualification": QUALIFICATION,
    }
    # Canonical comparison also distinguishes booleans from numeric settings.
    if digest_json(value) != digest_json(expected):
        raise ResearchError("Unsupported or changed draft-v2 protocol contract")
    return value


def load_protocol(path):
    return validate_protocol(read_json(Path(path)))


def candidate_key(subset, seed):
    if subset not in CANDIDATES or type(seed) is not int or seed not in SEEDS:
        raise ResearchError("Unregistered draft-v2 candidate or seed")
    return f"{subset}:{seed}"


def candidate_keys():
    return [candidate_key(subset, seed) for subset in CANDIDATES for seed in SEEDS]
