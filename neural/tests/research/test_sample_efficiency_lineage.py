import copy

import pytest
import torch

from src.artifacts.manifest import sha256_file
from src.research.artifacts import digest_json, read_run
from src.research.assessment import categorize_bundle
from src.research.calibration import build_raw_calibration_bundle, require_raw_calibration_bundle
from src.research.errors import ResearchError
from src.research.inference import run_asimov, run_toys
from src.research.sample_efficiency_lineage import ExperimentLineage, require_experiment_lineage
from src.research.sample_efficiency_training import publish_subset_discriminant
from src.research.templates import (bind_template_lineage, build_sample_efficiency_template,
                                    require_template_lineage)

from sample_efficiency_support import build_sample_efficiency_fixture


@pytest.fixture(autouse=True)
def single_thread():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def _valid_template(candidate, mapping):
    sample = lambda name, signal, value: {"name": name, "is_signal": signal, "yield": [value],
        "variance": [0.1], "covariance": [[0.1]], "sum_abs_weight": [value],
        "sum_positive_weight": [value], "sum_negative_weight": [0.0], "group_count": [10],
        "neff_signed": [10.0], "neff_abs": [10.0], "rho": [1.0], "bin_status": ["valid"]}
    return {"status": "valid", "dataset": "atlas2020_4lep", "role": "template",
        "candidate_id": candidate, "mapping_id": mapping, "mass_edges": [105.0, 140.0],
        "categories": [0], "active_bins": [0],
        "samples": [sample("background", False, 10.0), sample("signal", True, 2.0)],
        "issues": [], "structural_zero_evidence": {},
        "variance_convention": "sum_outer_products_of_group_bin_signed_weights"}


def test_raw_calibration_template_and_asimov_copy_exact_lineage(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path,
                                                                                template_groups=400)
    loaded = publish_subset_discriminant(tmp_path / "model", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    bundle = build_raw_calibration_bundle(prepared, loaded, base)
    require_raw_calibration_bundle(bundle, loaded)
    require_experiment_lineage(bundle.to_dict(), loaded.lineage)
    bound = build_sample_efficiency_template(prepared, loaded, bundle, base,
                                              mass_edges=[105.0, 140.0])
    require_template_lineage(bound, loaded.lineage)
    result = run_asimov(bound, protocol=base, injections=(1.0,),
                        experiment_lineage=loaded.lineage)
    assert result["expectation_kind"] == "model_self_asimov"
    assert result["experiment_lineage"] == loaded.lineage.to_dict()
    assert result["result_id"] == digest_json({key: value for key, value in result.items() if key != "result_id"})


def test_downstream_lineage_substitution_and_nonraw_are_rejected(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    first = publish_subset_discriminant(tmp_path / "first", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    second = publish_subset_discriminant(tmp_path / "second", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="engineered19", network_seed=42)
    bundle = build_raw_calibration_bundle(prepared, first, base)
    with pytest.raises(ResearchError):
        require_experiment_lineage(bundle.to_dict(), second.lineage)
    with pytest.raises(ResearchError):
        build_raw_calibration_bundle(prepared, first, base, transform="physical")
    forged = copy.deepcopy(bundle.to_dict())
    forged["experiment_lineage"]["experiment_cell_id"] = second.lineage["experiment_cell_id"]
    with pytest.raises(ResearchError):
        require_experiment_lineage(forged, first.lineage)


def test_capabilities_cross_prepared_and_handmade_template_are_rejected(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path / "one")
    loaded = publish_subset_discriminant(tmp_path / "model", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    other = build_sample_efficiency_fixture(tmp_path / "two")
    other_path = other[1].path / "events.jsonl"
    lines = other_path.read_text(encoding="utf-8").splitlines()
    identity, payload = lines[1].split("\t", 1)
    changed = __import__("json").loads(payload)
    changed["lep1_pt"] += 1.0
    lines[1] = identity + "\t" + __import__("json").dumps(changed, sort_keys=True, separators=(",", ":"))
    other_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    manifest_path = other[1].path / "manifest.json"
    manifest = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["events.jsonl"] = {"sha256": sha256_file(other_path),
                                             "size_bytes": other_path.stat().st_size}
    manifest["artifact_id"] = digest_json({key: value for key, value in manifest.items()
                                            if key != "artifact_id"})
    manifest_path.write_text(__import__("json").dumps(manifest, sort_keys=True, separators=(",", ":")),
                             encoding="utf-8", newline="\n")
    other_prepared = read_run(other[1].path, dataset=base["dataset"], protocol=base.to_dict(),
                              stages=("prepare",))
    with pytest.raises(ResearchError) as error:
        build_raw_calibration_bundle(other_prepared, loaded, base)
    assert error.value.status == "training_subset_binding_mismatch"
    with pytest.raises(ResearchError):
        ExperimentLineage(loaded.lineage.to_dict())
    bundle = build_raw_calibration_bundle(prepared, loaded, base)
    with pytest.raises(ResearchError):
        require_raw_calibration_bundle(bundle.to_dict(), loaded)
    with pytest.raises(ResearchError):
        bind_template_lineage(_valid_template(bundle["candidate_id"], bundle["mapping_id"]), bundle,
                              experiment_lineage=loaded.lineage)


def test_lineage_template_cannot_bypass_model_self_guard(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path,
                                                                                template_groups=400)
    loaded = publish_subset_discriminant(tmp_path / "model", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    bundle = build_raw_calibration_bundle(prepared, loaded, base)
    template = build_sample_efficiency_template(prepared, loaded, bundle, base,
                                                 mass_edges=[105.0, 140.0])
    with pytest.raises(ResearchError) as error:
        run_asimov(template, protocol=base, injections=(1.0,))
    assert error.value.status == "training_subset_binding_mismatch"
    with pytest.raises(ResearchError) as error:
        run_toys(template, count=1)
    assert error.value.status == "training_subset_binding_mismatch"
    with pytest.raises(ResearchError) as error:
        categorize_bundle(bundle.to_dict(), object())
    assert error.value.status == "training_subset_binding_mismatch"
