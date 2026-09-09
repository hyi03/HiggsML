"""Versioned software protocol, separately recording pending physics validation."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from .errors import ResearchError

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config/research_protocol_v2.json"

# New diagnostic rules are bound only by v2; v1 remains readable unchanged.
DIAGNOSTICS = {
    "training": "epoch_components_and_train_median_validation_mass_v1",
    "signed_mu": {
        "kind": "fixed_nominal_template_poisson_mle",
        "mu_bounds": [-20.0, 20.0],
        "positive_domain_fraction": 0.99999999,
        "injection": 0.0,
        "nuisance_policy": "fixed_nominal_no_T1_profiling",
    },
    "interval_calibration": "not_implemented_requires_separate_registration",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def protocol_dict(protocol):
    return protocol.to_dict() if isinstance(protocol, ResearchProtocol) else protocol


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ResearchError(f"{name} has missing or unknown fields")


def _number(value, name, *, minimum=0., maximum=None, integer=False, strict=True):
    if type(value) not in (int, float) or not math.isfinite(value) or (integer and type(value) is not int):
        raise ResearchError(f"{name} must be finite numeric" + (" integer" if integer else ""))
    if (value <= minimum if strict else value < minimum) or (maximum is not None and value > maximum):
        raise ResearchError(f"{name} outside supported range")


def _grid(value, name, support):
    if not isinstance(value,list) or len(value)<2:
        raise ResearchError(f"{name} requires an ordered grid")
    for x in value:
        _number(x,name,minimum=-float("inf"))
    if value[0]!=support[0] or value[-1]!=support[1] or any(b<=a for a,b in zip(value,value[1:])):
        raise ResearchError(f"{name} changed support or ordering")


def validate_protocol(raw, dataset):
    version = raw.get("schema_version") if isinstance(raw, dict) else None
    extra = ("diagnostics",) if version == "h4l-research-v2" else ()
    _keys(raw, ("schema_version","protocol_id","dataset","final_state","mass_window","luminosity_pb",
          "development_probability","roles","role_hash","seeds","training","calibration","g0","templates",
          "validation","protocol_scope","assessment_access","matrix_element","inference","stress", *extra), "protocol")
    if version not in {"h4l-research-v1", "h4l-research-v2"} or raw["dataset"] != dataset:
        raise ResearchError("research protocol dataset/schema mismatch")
    if extra and raw["diagnostics"] != DIAGNOSTICS:
        raise ResearchError("unsupported registered diagnostic contract")
    if dataset != "atlas2020_4lep" or raw["final_state"] != "2e2mu":
        raise ResearchError("pilot supports atlas2020_4lep 2e2mu only")
    if not isinstance(raw["protocol_id"],str) or not raw["protocol_id"].strip():
        raise ResearchError("protocol identity is required")
    expected_roles={"train":.4,"validation":.1,"calibration":.2,"template":.2,"assessment":.1}
    if raw["roles"] != expected_roles:
        raise ResearchError("role probabilities changed; implement a new protocol version")
    if raw["development_probability"] != .8 or raw["mass_window"] != [105.,140.] or raw["luminosity_pb"] != 10000.:
        raise ResearchError("split/support/luminosity contract changed")
    if raw["role_hash"] != "sha256:h4l-role-v1:group:big64:mod100" or raw["seeds"] != [42,43,44,45,46]:
        raise ResearchError("unsupported role hash or paired network seeds")
    if raw["assessment_access"] != "frozen_analysis_only" or raw["protocol_scope"] != "synthetic_software_defaults_not_physics_validation":
        raise ResearchError("research evidence/access scope changed")
    train=raw["training"]
    _keys(train,("max_epochs","patience","minimum_improvement","batch_size","learning_rate","weight_decay","warmup_epochs","ramp_epochs","adversary_bins"),"training")
    for key in ("max_epochs","patience","batch_size","warmup_epochs","ramp_epochs","adversary_bins"):
        _number(train[key],key,integer=True)
    if train["max_epochs"]!=200 or train["adversary_bins"]!=11 or train["patience"]>200 or train["warmup_epochs"]+train["ramp_epochs"]>200:
        raise ResearchError("unsupported frozen training schedule")
    _number(train["learning_rate"],"learning_rate")
    for key in ("minimum_improvement","weight_decay"):
        _number(train[key],key,strict=False)
    cal=raw["calibration"]
    strategies={"interpolation":"linear-bin-cdf_mass-centers","ties":"same-score-same-cdf","tails":"score-clamp_mass-reject","merge_order":"leftmost-failing-right-else-left"}
    _keys(cal,("mass_edges","score_edges","min_effective_count","min_cancellation_ratio",*strategies),"calibration")
    if any(cal[k]!=v for k,v in strategies.items()):
        raise ResearchError("unsupported calibration algorithm")
    _grid(cal["mass_edges"],"calibration mass_edges",raw["mass_window"])
    _grid(cal["score_edges"],"calibration score_edges",[0.,1.])
    _number(cal["min_effective_count"],"calibration min_effective_count")
    _number(cal["min_cancellation_ratio"],"calibration min_cancellation_ratio",maximum=1.)
    for section in ("g0","templates"):
        obj=raw[section]
        _keys(obj,("min_neff_signed","min_rho") if section=="g0" else ("mass_edges","score_categories","min_neff_signed","min_rho"),section)
        _number(obj["min_neff_signed"],f"{section} min_neff_signed")
        _number(obj["min_rho"],f"{section} min_rho",maximum=1.)
    _grid(raw["templates"]["mass_edges"],"template mass_edges",raw["mass_window"])
    if raw["templates"]["score_categories"]!=2 or not set(cal["mass_edges"]) <= set(raw["templates"]["mass_edges"]):
        raise ResearchError("template category/calibration-grid compatibility changed")
    inf=raw["inference"]
    _keys(inf,("pyhf_version","mu_bounds","confidence_levels","injections","toy_count","toy_seed","auxiliary_generation",
               "template_modifier","template_correlation","template_min_effective_count","template_min_cancellation_ratio",
               "outer_replicas","inner_toys","validation_status"),"inference")
    if inf["pyhf_version"]!="0.7.6" or inf["template_modifier"]!="shapesys" or inf["template_correlation"]!="independent_process_bins":
        raise ResearchError("unsupported likelihood implementation")
    if inf["confidence_levels"]!=[.68,.95] or inf["injections"]!=[0.,1.,2.] or inf["auxiliary_generation"] not in ("fixed","regenerated"):
        raise ResearchError("unsupported interval/injection/auxiliary contract")
    for value in inf["confidence_levels"]:
        _number(value,"confidence level",maximum=1.)
    for value in inf["injections"]:
        _number(value,"injection",strict=False)
    if not isinstance(inf["mu_bounds"],list) or len(inf["mu_bounds"])!=2 or inf["mu_bounds"][0]!=0.:
        raise ResearchError("mu bounds must start at physical zero")
    _number(inf["mu_bounds"][0],"lower mu bound",strict=False)
    _number(inf["mu_bounds"][1],"upper mu bound",minimum=2.)
    for key in ("toy_count","outer_replicas","inner_toys"):
        _number(inf[key],key,integer=True)
    _number(inf["toy_seed"],"toy_seed",integer=True,strict=False)
    if inf["inner_toys"]>inf["toy_count"]:
        raise ResearchError("T2 inner budget exceeds fixed inference budget")
    if inf["template_min_effective_count"]!=raw["templates"]["min_neff_signed"] or inf["template_min_cancellation_ratio"]!=raw["templates"]["min_rho"]:
        raise ResearchError("inference and template support thresholds disagree")
    if inf["validation_status"]!="unvalidated":
        raise ResearchError("independent T1 validation belongs in bound evidence, not protocol defaults")
    me=raw["matrix_element"]
    _keys(me,("reference_rtol","reference_atol","probability_semantics","score"),"matrix_element")
    _number(me["reference_rtol"],"reference_rtol")
    _number(me["reference_atol"],"reference_atol")
    if me["reference_rtol"]>1e-3 or me["reference_atol"]>1e-5 or me["probability_semantics"]!="nonnegative_densities_common_input_support" or me["score"]!="p_signal/(p_signal+p_background)":
        raise ResearchError("unsupported ME numerical contract")
    expected_validation={"repository_authority_validation":"not_run","scientific_numerical_validation":"pending_independent_reference",
                         "bound_mc_pilot":"not_run","matrix_element":"blocked_missing_reference","external_robustness":"not_run"}
    if raw["validation"]!=expected_validation:
        raise ResearchError("run validation evidence cannot overwrite software protocol evidence states")
    expected_stress={"amplitude":.1,"nuisance_bounds":[-1.,1.],"auxiliary":"normal",
        "modifiers":{"normalization":"normsys","shape":"histosys"},
        "interpolation":{"normsys":"code4","histosys":"code4p"},
        "reference_strategy":"one_frozen_reference_mapping_shared_across_methods","reference_candidate":"M3:42","allowed_directions":[-1,1],
        "shape_normalization":"fixed_total_background_signed_yield","t1_variance":"constant_relative_MC_variance"}
    if raw["stress"]!=expected_stress:
        raise ResearchError("unsupported frozen artificial stress contract")
    canonical(raw)  # Reject any residual non-finite values before binding bytes.


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ResearchError("duplicate research protocol JSON key")
        result[key]=value
    return result


@dataclass(frozen=True)
class ResearchProtocol:
    payload: bytes

    def to_dict(self):
        return json.loads(self.payload)

    @property
    def digest(self):
        return hashlib.sha256(self.payload).hexdigest()

    def __getitem__(self, key):
        return self.to_dict()[key]


def load_protocol(path=None, dataset="atlas2020_4lep"):
    try:
        raw = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8-sig"),object_pairs_hook=_unique_object)
        validate_protocol(raw,dataset)
        return ResearchProtocol(canonical(raw))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ResearchError):
            raise
        raise ResearchError("invalid research protocol") from exc
