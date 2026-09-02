from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import yaml

from src.config import InputBindingError


FEATURES = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ", "cos_theta_star",
    "cos_theta_1", "cos_theta_2", "phi_decay_planes", "phi_production_plane",
)
INPUT_COLUMNS = (
    "lep1_pt", "lep2_pt", "lep3_pt", "lep4_pt", "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "mZ1", "mZ2", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ", "cos_theta_star",
    "cos_theta_1", "cos_theta_2", "phi_decay_planes", "phi_production_plane", "m4l", "label",
    "split", "physical_weight", "train_weight", "source_sample", "source_entry", "runNumber",
    "eventNumber", "channelNumber",
)
FORBIDDEN_FEATURES = tuple(column for column in INPUT_COLUMNS if column not in FEATURES)
TARGET_LAMBDAS = (0.0, 0.05, 0.10, 0.20, 0.50)
BASE_SEED = 42


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _UniqueLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise InputBindingError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


_EXPECTED: dict[str, Any] = {
    "schema_version": "1.0",
    "protocol_id": "adversarial-mlp-protocol-v1",
    "features": list(FEATURES),
    "input_columns": list(INPUT_COLUMNS),
    "forbidden_features": list(FORBIDDEN_FEATURES),
    "dtypes": {"frame_float": "float64", "model_float": "float32", "label_and_bin": "int64"},
    "classifier": {
        "widths": [15, 64, 64, 32, 1], "activation": "silu",
        "layer_norm": {"affine": True, "eps": 1.0e-5}, "linear_bias": True,
        "dropout": 0.10, "parameter_count": 7617,
    },
    "adversary": {
        "widths": [1, 32, 32, 11], "activation": "silu",
        "layer_norm": {"affine": True, "eps": 1.0e-5}, "linear_bias": True,
        "bins": 11,
        "mass_edges_gev": [105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0, 160.0],
        "parameter_count": 1611,
    },
    "gradient_reversal": {"forward": "identity", "backward": "negative_lambda_scale"},
    "losses": {
        "classification": "weighted_bce_with_logits",
        "adversarial": "bin_balanced_background_cross_entropy",
        "physical_weight_transform": "absolute",
        "empty_effective_background": "differentiable_zero",
        "bin_balance_rtol": 0.0,
        "bin_balance_atol": 1.0e-7,
    },
    "scaler": {"fitting_dtype": "float64", "model_dtype": "float32", "variance_ddof": 0, "zero_variance_scale": 1.0},
    "optimization": {"optimizer": "adamw", "learning_rate": 1.0e-3, "weight_decay": 1.0e-4, "batch_size": 1024, "maximum_epochs": 200, "drop_last": False},
    "determinism": {"device": "cpu", "base_seed": 42, "fold_indices": [0, 1, 2, 3, 4], "data_loader_workers": 0, "deterministic_algorithms": True, "target_lambdas": list(TARGET_LAMBDAS)},
    "schedule": {"warmup_epochs": 5, "ramp_epochs": 10, "first_full_lambda_epoch": 15},
    "early_stopping": {"metric": "validation_weighted_auc", "patience": 20, "minimum_improvement": 1.0e-4},
    "checkpoint": {
        "in_memory_only": True, "deep_cpu_copy": True, "bind_protocol_sha256": True,
        "fields": ["protocol_sha256", "feature_tuple", "scaler", "fold_index", "fold_seed", "target_lambda", "best_epoch", "best_validation_weighted_auc", "classifier_state_dict", "adversary_state_dict"],
    },
    "result": {
        "epoch_fields": ["epoch", "lambda_effective", "train_cls_loss", "train_adv_loss", "train_total_loss", "validation_weighted_auc", "is_best", "duration_seconds", "events_per_second"],
        "summary_fields": ["epochs_completed", "stopped_early", "best_epoch", "best_validation_weighted_auc"],
        "environment_fields": ["os", "architecture", "python", "pytorch", "device", "dtype", "threads", "data_loader_workers", "deterministic_algorithms"],
    },
    "folding": {
        "count": 5, "algorithm": "sha256_identity_v1", "encoding": "utf-8",
        "separator_hex": "00", "digest_prefix_bytes": 8, "byte_order": "big", "modulo": 5,
    },
    "working_points": {"loose": 0.50, "medium": 0.20, "tight": 0.10},
    "qualification": {
        "auc_minimum": 0.80, "ks_maximum": 0.10,
        "signal_efficiency_strictly_greater": True,
        "auc_tie_rtol": 0.0, "auc_tie_atol": 1.0e-6,
    },
    "final_fit": {
        "scaler_scope": "full_development", "seed": 42,
        "epochs_rule": "median_fold_best_epoch", "early_stopping": False,
    },
    "development_artifacts": {
        "oof_columns": ["target_lambda", "source_sample", "source_entry", "fold_index", "label", "m4l", "physical_weight", "train_weight", "score"],
        "fold_metric_columns": ["target_lambda", "fold_index", "fold_seed", "epoch", "lambda_effective", "train_cls_loss", "train_adv_loss", "train_total_loss", "validation_weighted_auc", "is_best", "duration_seconds", "events_per_second", "best_epoch", "best_validation_weighted_auc", "epochs_completed", "stopped_early"],
        "candidate_metric_columns": ["target_lambda", "weighted_oof_auc", "loose_threshold", "loose_target_background_efficiency", "loose_achieved_background_efficiency", "loose_signal_efficiency", "loose_ks", "medium_threshold", "medium_target_background_efficiency", "medium_achieved_background_efficiency", "medium_signal_efficiency", "medium_ks", "tight_threshold", "tight_target_background_efficiency", "tight_achieved_background_efficiency", "tight_signal_efficiency", "tight_ks", "eligible", "rejection_reasons_json"],
        "required_paths": ["config.yaml", "artifacts/candidate_metrics.csv", "artifacts/fold_metrics.csv", "artifacts/qualification.json", "artifacts/working_points.json", "predictions/oof_scores.csv.gz", "plots/auc_vs_lambda.png", "plots/ks_vs_lambda.png", "plots/oof_roc.png", "plots/oof_mass_sculpting.png", "artifacts/manifest.json"],
        "eligible_only_paths": ["model/model.pt", "model/scaler.json"],
        "canonical_json_files": ["artifacts/qualification.json", "artifacts/working_points.json", "artifacts/manifest.json"],
    },
}


@dataclass(frozen=True)
class TrainingProtocol:
    protocol_id: str
    features: tuple[str, ...]
    target_lambdas: tuple[float, ...]
    raw: dict[str, Any]
    payload: bytes
    sha256: str

    @property
    def batch_size(self) -> int:
        return int(self.raw["optimization"]["batch_size"])

    @property
    def maximum_epochs(self) -> int:
        return int(self.raw["optimization"]["maximum_epochs"])

    @property
    def patience(self) -> int:
        return int(self.raw["early_stopping"]["patience"])

    @property
    def minimum_improvement(self) -> float:
        return float(self.raw["early_stopping"]["minimum_improvement"])

    @property
    def base_seed(self) -> int:
        return int(self.raw["determinism"]["base_seed"])

    @property
    def warmup_epochs(self) -> int:
        return int(self.raw["schedule"]["warmup_epochs"])

    @property
    def ramp_epochs(self) -> int:
        return int(self.raw["schedule"]["ramp_epochs"])

    @property
    def fold_count(self) -> int:
        return int(self.raw["folding"]["count"])

    @property
    def working_points(self) -> tuple[tuple[str, float], ...]:
        return tuple((name, float(value)) for name, value in self.raw["working_points"].items())


def _strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return list(actual) == list(expected) and all(
            _strict_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


def validate_training_protocol_snapshot(raw: Any) -> dict[str, Any]:
    """Validate an already hash-bound raw protocol without reading a repository file."""
    if not _strict_equal(raw, _EXPECTED):
        raise InputBindingError("sealed adversarial MLP protocol changed")
    return raw


def load_training_protocol(path: str | Path) -> TrainingProtocol:
    try:
        payload = Path(path).read_bytes()
        raw = yaml.load(payload.decode("utf-8"), Loader=_UniqueLoader)
    except InputBindingError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise InputBindingError("unable to load sealed adversarial MLP protocol") from exc
    validate_training_protocol_snapshot(raw)
    return TrainingProtocol(
        protocol_id=str(raw["protocol_id"]),
        features=tuple(raw["features"]),
        target_lambdas=tuple(float(value) for value in raw["determinism"]["target_lambdas"]),
        raw=raw,
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
    )
