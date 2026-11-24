import csv
import hashlib
import json

import pytest

from higgsml.errors import ResearchError
from higgsml.inference.report_exports import publish_analysis_exports


class InputRun:
    def __init__(self, artifact_id, stage, payloads, *, prepared_id="prepared"):
        self.manifest = {"artifact_id": artifact_id, "stage": stage, "status": "complete",
                         "context": {"prepared_artifact_id": prepared_id}, "files": {}}
        self.payloads = payloads

    def read_json(self, name):
        return self.payloads[name]


class OutputRun:
    def __init__(self, path):
        self.path = path
        self.manifest = {"dataset": "atlas2020_4lep", "protocol_sha256": "p", "files": {},
                         "software": {"python": "3.12"}, "upstreams": []}

    def register_file(self, name):
        payload = (self.path / name).read_bytes()
        self.manifest["files"][name] = {"sha256": hashlib.sha256(payload).hexdigest(),
                                        "size_bytes": len(payload)}

    def write_json(self, name, value):
        (self.path / name).write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        self.register_file(name)


def model(candidate, seed, auc, *, groups=None):
    return {"candidate": candidate, "seed": seed, "groups": groups, "representation": "engineered19",
            "ordered_inputs": ["x"], "status": "trained", "validation_absolute_weight_auc": auc,
            "selected_epoch": 2, "checkpoint_rule": "max_validation_absolute_weight_auc",
            "target_lambda": 0.0, "effective_lambda": 0.0,
            "model_id": f"{candidate}-{seed}-{groups}", "protocol_id": "protocol",
            "history": [{"epoch": 1, "loss": 1.0, "validation_absolute_weight_auc": auc - .01},
                        {"epoch": 2, "loss": .9, "validation_absolute_weight_auc": auc}]}


def test_analysis_export_reports_five_seed_auc_independently_of_inference(tmp_path):
    training = []
    comparisons = []
    for seed in range(42, 47):
        training.append(InputRun(f"m0-{seed}", "train", {"model.json": model("M0c", seed, .80)}))
        training.append(InputRun(f"ma-{seed}", "train", {"model.json": model("M3", seed, .85, groups=["A"])}))
        comparisons.append({"seed": seed, "status": "feature_combination_incomplete",
                            "comparison_cohort_id": "cohort", "nonempty_combinations": []})
    report = {"prepared_artifact_id": "prepared", "primary_comparison_cohort_id": "cohort",
              "feature_combination_comparisons": comparisons,
              "training_state_history": {"M3:42:groups=A": [{"stage": "train", "status": "trained",
                                                               "artifact_id": "ma-42"}]}}
    output = OutputRun(tmp_path)
    result = publish_analysis_exports(output, report, training_runs=training)

    row = next(row for row in result["feature_auc_summary"] if row["subset"] == "A")
    assert row["status"] == row["auc_status"] == "valid"
    assert row["inference_status"] == "incomplete"
    assert row["median_auc"] == pytest.approx(.85)
    assert row["median_delta_auc_vs_m0c"] == pytest.approx(.05)
    with (tmp_path / "feature_metrics.csv").open(encoding="utf-8", newline="") as stream:
        metric = next(row for row in csv.DictReader(stream) if row["candidate_key"] == "M3:42:groups=A")
    assert float(metric["raw_validation_auc"]) == pytest.approx(.85)
    assert float(metric["delta_auc_vs_m0c"]) == pytest.approx(.05)
    dictionary = json.loads((tmp_path / "data_dictionary.json").read_text(encoding="utf-8"))
    assert dictionary["tables"]["feature_metrics.csv"]["fields"]["delta_auc_vs_m0c"]["formula"]
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["training_artifact_ids"] == [item.manifest["artifact_id"] for item in training]
    assert provenance["export_file_receipts"]["models.csv"]["sha256"]
    assert provenance["export_file_receipts"]["analysis_records.jsonl"]["sha256"]
    first_jsonl = json.loads((tmp_path / "analysis_records.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first_jsonl["table"] == "models.csv"


def test_analysis_export_rejects_mixed_prepared_populations(tmp_path):
    left = InputRun("left", "train", {"model.json": model("M0c", 42, .8)}, prepared_id="p1")
    right = InputRun("right", "train", {"model.json": model("M3", 42, .9, groups=["A"])}, prepared_id="p2")
    with pytest.raises(ResearchError, match="cannot mix prepared populations"):
        publish_analysis_exports(OutputRun(tmp_path), {}, training_runs=[left, right])


def test_analysis_export_publishes_mass_input_pair_and_slice_support(tmp_path):
    pair = {"subset":"BC", "seed":42, "status":"valid",
            "on_candidate_key":"M3:42:groups=BC", "off_candidate_key":"M3:42:groups=BC:m4l=off",
            "auc_on":.8, "auc_off":.75, "delta_auc_on_minus_off":.05,
            "width68_on":8., "width68_off":10., "delta_width68_on_minus_off":-2.,
            "relative_w68_improvement_from_m4l":.2,
            "mass_slices":[{"slice_index":0,"mass_low":105.,"mass_high":110.,"status":"valid",
                "auc_on":.7,"auc_off":.6,"delta_auc_on_minus_off":.1,
                "class_support":{"0":{"row_count":3,"sum_absolute_weight":4.,"effective_count":2.},
                                 "1":{"row_count":2,"sum_absolute_weight":2.,"effective_count":2.}}}]}
    report = {"mass_input_comparisons":[{"seed":42,"comparison_cohort_id":"cohort",
        "mass_only_baseline":{"candidate_key":"M0c:42","validation_absolute_weight_auc":.7,"width68":11.},
        "pairs":[pair]}], "mass_input_summary":{"combinations":[{"subset":"BC","status":"valid",
            "median_delta_auc_on_minus_off":.05,"min_delta_auc_on_minus_off":.05,"max_delta_auc_on_minus_off":.05,
            "median_delta_width68_on_minus_off":-2.,"min_delta_width68_on_minus_off":-2.,"max_delta_width68_on_minus_off":-2.,
            "median_relative_w68_improvement_from_m4l":.2,"min_relative_w68_improvement_from_m4l":.2,
            "max_relative_w68_improvement_from_m4l":.2}]}}
    publish_analysis_exports(OutputRun(tmp_path), report)
    with (tmp_path / "mass_input_metrics.csv").open(encoding="utf-8", newline="") as stream:
        metric = next(csv.DictReader(stream))
    assert metric["off_candidate_key"].endswith(":m4l=off")
    assert float(metric["mass_only_auc"]) == pytest.approx(.7)
    with (tmp_path / "mass_slice_auc.csv").open(encoding="utf-8", newline="") as stream:
        mass = next(csv.DictReader(stream))
    assert int(mass["background_row_count"]) == 3
    assert float(mass["delta_auc_on_minus_off"]) == pytest.approx(.1)
