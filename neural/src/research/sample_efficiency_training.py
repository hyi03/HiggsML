"""Receipt-bound single-cell training for the sample-efficiency experiment."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .artifacts import LoadedRun, ResearchRun, read_run
from .data import load_research_data
from .discriminants import ResearchClassifier, digest, train_discriminant
from .errors import ResearchError
from .protocol import ResearchProtocol, canonical
from .representations import representation_features
from .sample_efficiency_lineage import ExperimentLineage, _lineage_from_verified_model, require_experiment_lineage
from .sample_efficiency_protocol import SampleEfficiencyProtocol
from .training_subsets import TrainingSubset, load_training_subset, summarize_training_rows


MODEL_SCHEMA = "research-discriminant-v2"
MODEL_STAGE = "sample-efficiency-train"
ARCHITECTURE_VARIANT = "baseline-fixed64x64x32"
_LOADED_TOKEN = object()
_V1_REQUIRED = {
    "schema_version", "candidate", "representation", "groups", "ordered_inputs", "dataset", "protocol_id",
    "seed", "architecture", "scaler", "optimizer_class_absolute_weight_means", "mass_bin_boundaries",
    "state_dict", "history", "selected_epoch", "target_lambda", "effective_lambda", "checkpoint_rule",
    "validation_absolute_weight_auc", "diagnostics", "status", "eligibility_gate", "model_id",
}
_V2_EXTRA = {
    "base_research_protocol_sha256", "sample_efficiency_protocol_sha256", "training_subset_artifact_id",
    "training_subset_id", "membership_digest", "prepared_artifact_id", "population_id",
    "sample_fraction_target", "sample_draw_seed", "sample_draw_seed_or_full", "full_endpoint_canonicalized",
    "network_seed", "representation_id", "architecture_variant", "trainable_parameter_count",
    "training_summary_by_label", "training_summary_total", "train_fitted_statistics_source",
    "experiment_cell_id", "pairing_id",
}


def _fail(message):
    raise ResearchError(message, status="training_subset_binding_mismatch")


def _finite_json(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            _fail("nonfinite v2 model value")
        return
    if type(value) is list:
        for item in value:
            _finite_json(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _finite_json(item)
        return
    _fail("invalid v2 model JSON value")


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ids(model):
    common = [model["sample_efficiency_protocol_sha256"], model["training_subset_artifact_id"],
              model["training_subset_id"], model["sample_fraction_target"], model["sample_draw_seed_or_full"],
              model["network_seed"], "raw", model["architecture_variant"]]
    experiment = common[:3] + [model["representation_id"]] + common[3:]
    return (hashlib.sha256(canonical(experiment)).hexdigest(),
            hashlib.sha256(canonical(common)).hexdigest())


def _representation(selection, overlay, representation_id):
    if representation_id not in overlay["representations"]:
        _fail("representation is outside the sample-efficiency protocol")
    if representation_id == "decay7":
        return "M2", "decay7", None
    if representation_id == "engineered19":
        return "M3", "engineered19", None
    compact = selection["compact_candidate"]
    if representation_id != compact["representation_id"]:
        _fail("compact representation differs from the frozen candidate")
    expected = list(representation_features(compact["representation"], groups=compact["groups"]))
    if compact["ordered_inputs"] != expected or compact["input_dimension"] != len(expected):
        _fail("compact representation descriptor mismatch")
    return "M3", compact["representation"], compact["groups"]


def validate_discriminant_v2(model, *, selection=None, base=None, overlay=None):
    if type(model) is not dict or model.get("schema_version") != MODEL_SCHEMA:
        _fail("invalid v2 discriminant schema")
    base_raw = base.to_dict() if isinstance(base, ResearchProtocol) else None
    history_required = base_raw is not None and "diagnostics" in base_raw
    allowed = _V1_REQUIRED | _V2_EXTRA | ({"history_contract"} if history_required else set())
    if base is None and "history_contract" in model:
        allowed.add("history_contract")
    if set(model) != allowed:
        _fail("v2 discriminant has missing or unknown fields")
    _finite_json(model)
    content = {key: value for key, value in model.items() if key != "model_id"}
    if digest(content) != model["model_id"]:
        _fail("v2 model digest mismatch")
    for field in ("base_research_protocol_sha256", "sample_efficiency_protocol_sha256",
                  "training_subset_artifact_id", "training_subset_id", "membership_digest",
                  "prepared_artifact_id", "population_id", "experiment_cell_id", "pairing_id"):
        if not _sha(model[field]):
            _fail(f"invalid v2 digest field: {field}")
    if (type(model.get("scaler")) is not dict or type(model.get("training_summary_total")) is not dict
            or type(model.get("training_summary_by_label")) is not list
            or type(model.get("ordered_inputs")) is not list
            or any(type(name) is not str or not name for name in model["ordered_inputs"])
            or (model.get("groups") is not None and (type(model["groups"]) is not list
                                                     or any(type(group) is not str for group in model["groups"])))):
        _fail("invalid nested v2 model schema")
    if model["seed"] != model["network_seed"] or type(model["network_seed"]) is not int:
        _fail("v2 network seed mismatch")
    if model["architecture_variant"] != ARCHITECTURE_VARIANT or model["target_lambda"] != 0:
        _fail("unsupported v2 architecture or lambda")
    full = model["sample_fraction_target"] == 1.0
    if (type(model["sample_fraction_target"]) is not float
            or not 0.0 < model["sample_fraction_target"] <= 1.0
            or model["full_endpoint_canonicalized"] is not full
            or (full and (model["sample_draw_seed"] is not None or model["sample_draw_seed_or_full"] != "full"))
            or (not full and (type(model["sample_draw_seed"]) is not int
                              or model["sample_draw_seed_or_full"] != model["sample_draw_seed"]))):
        _fail("v2 fraction/draw canonicalization mismatch")
    if selection is not None:
        if not isinstance(selection, TrainingSubset):
            _fail("validated training subset is required")
        bound = {"training_subset_artifact_id": selection["training_subset_artifact_id"],
                 "training_subset_id": selection["training_subset_id"],
                 "membership_digest": selection["membership_digest"],
                 "prepared_artifact_id": selection["prepared_artifact_id"],
                 "population_id": selection["population_id"],
                 "sample_efficiency_protocol_sha256": selection["sample_efficiency_protocol_sha256"],
                 "sample_fraction_target": selection["sample_fraction_target"],
                 "sample_draw_seed": selection["sample_draw_seed"],
                 "sample_draw_seed_or_full": selection["sample_draw_seed_or_full"],
                 "training_summary_by_label": selection["summary_by_label"],
                 "training_summary_total": selection["summary_total"]}
        if any(canonical(model[key]) != canonical(value) for key, value in bound.items()):
            _fail("v2 model differs from training subset selection")
    if base is not None and (not isinstance(base, ResearchProtocol)
                             or model["base_research_protocol_sha256"] != base.digest
                             or model["protocol_id"] != digest(base.to_dict())
                             or model["dataset"] != base["dataset"]):
        _fail("v2 base protocol mismatch")
    if base is not None:
        expected_history = ({
            "version": base_raw["diagnostics"]["training"],
            "classification_loss": "sum_train_normalized_absolute_weight_BCE / train_rows; online pre-update batches",
            "adversary_loss": "sum_background_normalized_absolute_weight_CE / sum_background_weights; online pre-update batches",
            "loss": "unweighted mean of batch composite losses; not classifier objective under gradient reversal",
            "threshold": "recomputed each epoch from train background absolute-weight median; validation evaluation only",
            "selection": "diagnostics never select checkpoint",
        } if history_required else None)
        if (history_required and canonical(model["history_contract"]) != canonical(expected_history)):
            _fail("v2 history contract mismatch")
    if overlay is not None and (not isinstance(overlay, SampleEfficiencyProtocol)
                                or model["sample_efficiency_protocol_sha256"] != overlay.digest):
        _fail("v2 overlay mismatch")
    if overlay is not None:
        if (model["network_seed"] not in overlay["network_seeds"]
                or model["representation_id"] not in overlay["representations"]
                or not any(canonical(model["sample_fraction_target"]) == canonical(value)
                           for value in overlay["sample_fractions"])
                or (not full and model["sample_draw_seed"] not in overlay["sample_draw_seeds"])):
            _fail("v2 experiment coordinate is outside the overlay")
    if selection is not None and overlay is not None:
        candidate, representation, groups = _representation(selection, overlay, model["representation_id"])
        names = list(representation_features(representation, groups=groups))
        if (model["candidate"] != candidate or model["representation"] != representation
                or model["groups"] != groups or model["ordered_inputs"] != names):
            _fail("v2 representation mapping mismatch")
    else:
        names = model["ordered_inputs"]
    expected_architecture = [len(names), 64, 64, 32, 1]
    parameters = sum(parameter.numel() for parameter in ResearchClassifier(len(names)).parameters())
    if (model["architecture"] != expected_architecture or model["trainable_parameter_count"] != parameters
            or model["scaler"].get("fitting_rows") != model["training_summary_total"].get("row_count")
            or model["train_fitted_statistics_source"] != model["training_subset_id"]):
        _fail("v2 train-fitted metadata mismatch")
    experiment, pairing = _ids(model)
    if model["experiment_cell_id"] != experiment or model["pairing_id"] != pairing:
        _fail("v2 experiment or pairing ID mismatch")
    return model


def _verified(run, base, stage, name):
    if not isinstance(run, LoadedRun):
        _fail(f"validated {name} run required")
    try:
        return read_run(run.path, dataset=base["dataset"], protocol=base.to_dict(), stages=(stage,))
    except ResearchError as exc:
        raise ResearchError(f"invalid {name} run", status="training_subset_binding_mismatch") from exc


def _train_model(prepared, selection, base, overlay, representation_id, network_seed, architecture_variant):
    if architecture_variant != ARCHITECTURE_VARIANT or network_seed not in overlay["network_seeds"]:
        _fail("architecture or network seed is outside the protocol")
    candidate, _, groups = _representation(selection, overlay, representation_id)
    frame = load_research_data(prepared.file("events.jsonl"), base["dataset"], base)
    if frame.attrs.get("population_id") != selection["population_id"]:
        _fail("prepared frame population differs from subset")
    member_groups = set(selection["event_group_ids"])
    if any(group in member_groups for group in frame.loc[frame.role != "train", "event_group_id"]):
        _fail("training subset member appears in a non-train role")
    train_groups = set(frame.loc[frame.role == "train", "event_group_id"])
    if not member_groups <= train_groups:
        _fail("training subset member is absent from prepared train data")
    selected_train = frame.loc[(frame.role == "train") & frame.event_group_id.isin(member_groups)].copy()
    summary = summarize_training_rows(selected_train)
    if canonical(summary) != canonical({"summary_by_label": selection["summary_by_label"],
                                        "summary_total": selection["summary_total"]}):
        _fail("actual training subset summary mismatch")
    validation = frame.loc[frame.role == "validation"].copy()
    training_frame = frame.loc[(frame.role == "train") & frame.event_group_id.isin(member_groups)
                               | (frame.role == "validation")].copy()
    if len(training_frame) != len(selected_train) + len(validation):
        _fail("validation preservation mismatch")
    model = train_discriminant(training_frame, base, candidate=candidate, seed=network_seed,
                               target_lambda=0.0, groups=groups)
    model.pop("model_id")
    model["schema_version"] = MODEL_SCHEMA
    model.update(base_research_protocol_sha256=base.digest,
        sample_efficiency_protocol_sha256=overlay.digest,
        training_subset_artifact_id=selection["training_subset_artifact_id"],
        training_subset_id=selection["training_subset_id"], membership_digest=selection["membership_digest"],
        prepared_artifact_id=selection["prepared_artifact_id"], population_id=selection["population_id"],
        sample_fraction_target=selection["sample_fraction_target"], sample_draw_seed=selection["sample_draw_seed"],
        sample_draw_seed_or_full=selection["sample_draw_seed_or_full"],
        full_endpoint_canonicalized=selection["sample_fraction_target"] == 1.0,
        network_seed=network_seed, representation_id=representation_id,
        architecture_variant=architecture_variant,
        trainable_parameter_count=sum(parameter.numel() for parameter in ResearchClassifier(len(model["ordered_inputs"])).parameters()),
        training_summary_by_label=selection["summary_by_label"], training_summary_total=selection["summary_total"],
        train_fitted_statistics_source=selection["training_subset_id"])
    model["experiment_cell_id"], model["pairing_id"] = _ids(model)
    model["model_id"] = digest(model)
    return validate_discriminant_v2(model, selection=selection, base=base, overlay=overlay)


@dataclass(frozen=True, init=False)
class LoadedSubsetDiscriminant:
    run: LoadedRun
    model: dict
    lineage: ExperimentLineage
    _capability: object

    def __init__(self, run, model, lineage, *, _token=None):
        if _token is not _LOADED_TOKEN:
            _fail("sample-efficiency model handle must come from its verified reader")
        object.__setattr__(self, "run", run)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "lineage", lineage)
        object.__setattr__(self, "_capability", _LOADED_TOKEN)


def require_loaded_subset_discriminant(value):
    if (not isinstance(value, LoadedSubsetDiscriminant)
            or getattr(value, "_capability", None) is not _LOADED_TOKEN):
        _fail("verified sample-efficiency model handle is required")
    try:
        reread = read_run(value.run.path, dataset=value.model["dataset"],
                          protocol=value.run.read_json("protocol.json"), stages=(MODEL_STAGE,))
        model = reread.read_json("model.json")
    except (ResearchError, KeyError, TypeError) as exc:
        raise ResearchError("invalid sample-efficiency model handle",
                            status="training_subset_binding_mismatch") from exc
    if (canonical(model) != canonical(value.model)
            or reread.manifest["artifact_id"] != value.lineage["source_model_artifact_id"]
            or model.get("model_id") != value.lineage["model_id"]):
        _fail("sample-efficiency model handle changed after verification")
    require_experiment_lineage({"experiment_lineage": value.lineage.to_dict()}, value.lineage)
    return value


def predict_subset_discriminant(loaded, frame):
    loaded = require_loaded_subset_discriminant(loaded)
    from .discriminants import _predict_discriminant_payload
    return _predict_discriminant_payload(loaded.model, frame)


def load_bound_prepared_role(prepared, loaded, base, role):
    loaded = require_loaded_subset_discriminant(loaded)
    prepared = _verified(prepared, base, "prepare", "prepared")
    if prepared.manifest["artifact_id"] != loaded.lineage["prepared_artifact_id"]:
        _fail("prepared run differs from sample-efficiency model")
    frame = load_research_data(prepared.file("events.jsonl"), base["dataset"], base)
    if frame.attrs.get("population_id") != loaded.lineage["population_id"]:
        _fail("prepared population differs from sample-efficiency model")
    selected = frame.loc[frame.role == role].copy()
    if selected.empty or set(selected.role) != {role}:
        _fail(f"prepared run has no bound {role} role")
    return selected


def publish_subset_discriminant(output_dir, *, allowed_root, prepared, freeze_run, subset_run,
                                base, overlay, fraction, draw, representation_id, network_seed,
                                architecture_variant=ARCHITECTURE_VARIANT):
    prepared = _verified(prepared, base, "prepare", "prepared")
    freeze_run = _verified(freeze_run, base, "compact-freeze", "compact-freeze")
    subset_run = _verified(subset_run, base, "training-subsets", "training-subsets")
    selection = load_training_subset(subset_run, prepared=prepared, freeze_run=freeze_run,
                                     base=base, overlay=overlay, fraction=fraction, draw=draw)
    model = _train_model(prepared, selection, base, overlay, representation_id, network_seed,
                         architecture_variant)
    with ResearchRun(output_dir, allowed_root=allowed_root, stage=MODEL_STAGE, dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=[prepared, freeze_run, subset_run],
                     context={"experiment_cell_id": model["experiment_cell_id"], "pairing_id": model["pairing_id"]}) as run:
        run.write_json("sample-efficiency-protocol.json", overlay.to_dict())
        run.write_json("model.json", model)
    return read_subset_discriminant_run(output_dir, prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, base=base, overlay=overlay, fraction=fraction, draw=draw,
        representation_id=representation_id, network_seed=network_seed,
        architecture_variant=architecture_variant)


def read_subset_discriminant_run(run, *, prepared, freeze_run, subset_run, base, overlay,
                                 fraction, draw, representation_id, network_seed,
                                 architecture_variant=ARCHITECTURE_VARIANT):
    prepared = _verified(prepared, base, "prepare", "prepared")
    freeze_run = _verified(freeze_run, base, "compact-freeze", "compact-freeze")
    subset_run = _verified(subset_run, base, "training-subsets", "training-subsets")
    run_path = run.path if isinstance(run, LoadedRun) else run
    try:
        run = read_run(run_path, dataset=base["dataset"], protocol=base.to_dict(), stages=(MODEL_STAGE,))
    except ResearchError as exc:
        raise ResearchError("invalid sample-efficiency model run", status="training_subset_binding_mismatch") from exc
    expected_upstreams = [{"artifact_id": item.manifest["artifact_id"], "stage": item.manifest["stage"],
                           "path": str(item.path)} for item in (prepared, freeze_run, subset_run)]
    actual_upstreams = run.manifest.get("upstreams")
    if actual_upstreams != expected_upstreams or run.read_json("sample-efficiency-protocol.json") != overlay.to_dict():
        _fail("sample-efficiency model run binding mismatch")
    selection = load_training_subset(subset_run, prepared=prepared, freeze_run=freeze_run,
                                     base=base, overlay=overlay, fraction=fraction, draw=draw)
    model = run.read_json("model.json")
    validate_discriminant_v2(model, selection=selection, base=base, overlay=overlay)
    if (model["representation_id"] != representation_id or model["network_seed"] != network_seed
            or model["architecture_variant"] != architecture_variant):
        _fail("sample-efficiency model request mismatch")
    lineage = _lineage_from_verified_model(model, source_model_artifact_id=run.manifest["artifact_id"])
    return LoadedSubsetDiscriminant(run, model, lineage, _token=_LOADED_TOKEN)
