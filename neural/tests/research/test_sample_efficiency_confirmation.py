from __future__ import annotations

import json

import pytest

from src.artifacts.manifest import sha256_file
from src.research.artifacts import ResearchRun, digest_json, read_run
from src.research.data import population_digest
from src.research.errors import ResearchError, ResearchStateError
from src.research.protocol import canonical
import src.research.sample_efficiency_confirmation as confirmation

from sample_efficiency_support import build_sample_efficiency_fixture


def _package(path, base, overlay, freeze, freeze_artifact_id, differences, *,
             groups=("confirm-a", "confirm-b"), source_kind="synthetic",
             mutate_receipts=None):
    identities = [{"event_group_id": group, "label": index, "role": "assessment",
                   "split": "development", "dataset": base["dataset"]}
                  for index, group in enumerate(groups)]
    population = population_digest({(item["event_group_id"], item["label"],
                                    item["split"], item["dataset"]) for item in identities},
                                   base["dataset"])
    receipts = []
    for index, (role, stage, kind, pointer) in enumerate(
        confirmation.EVALUATION_RECEIPT_SPECS,
    ):
        representation = (freeze["candidate"]["representation_id"] if kind == "compact"
                          else "engineered19" if kind == "reference" else "shared")
        receipts.append({
            "role": role,
            "representation_id": representation,
            "population_id": population,
            "artifact_id": digest_json({"artifact": index}),
            "stage": stage,
            "sha256": digest_json({"payload": index}),
            "pointer": pointer,
        })
    if mutate_receipts is not None:
        mutate_receipts(receipts)
    header = confirmation.expected_header(base, overlay, freeze, freeze_artifact_id)
    header.update(source_kind=source_kind, evaluation_package_id=digest_json(receipts))
    multiplicities = [digest_json({"replicate": index}) for index in range(len(differences))]
    replicates = [{"index": index, "multiplicity_digest": multiplicities[index],
                   "compact_w68": value, "reference_w68": 0.0,
                   "difference": value, "compact_pointer": f"/compact/{index}",
                   "reference_pointer": f"/reference/{index}"}
                  for index, value in enumerate(differences)]
    payload = dict(header, population_id=population,
        compact_representation=freeze["candidate"]["representation_id"],
        reference_representation="engineered19",
        canonical_event_group_order=sorted(groups),
        multiplicity_plan_id=digest_json({"seed": overlay["noninferiority"]["bootstrap_seed"],
            "unit": "event_group_id", "group_order": sorted(groups), "replicates": multiplicities}),
        replicates=replicates, evaluation_artifact_receipts=receipts,
        validation_scope=("synthetic_software_validation" if source_kind == "synthetic"
                          else "controlled_mc_external_pending"), payload_id=None)
    payload["payload_id"] = digest_json({key: value for key, value in payload.items()
                                          if key != "payload_id"})
    path.write_bytes(canonical(header) + b"\n" + b"".join(canonical(item) + b"\t\n" for item in identities)
                     + b"--PAYLOAD--\n" + canonical(payload) + b"\n")
    return payload


def _exclusion(path, dataset, groups, population_id):
    value = {"schema_version": confirmation.EXCLUSION_SCHEMA, "dataset": dataset,
             "population_id": population_id, "event_group_ids": sorted(groups)}
    value["identity_set_id"] = digest_json(value)
    path.write_bytes(canonical(value) + b"\n")


def _required_exclusions(tmp_path, base, overlay, *,
                         discovery_groups=("old-a",), learning_groups=("old-b",)):
    discovery = tmp_path / "excluded-discovery.json"
    learning = tmp_path / "excluded-learning.json"
    _exclusion(discovery, base["dataset"], discovery_groups,
               "synthetic-discovery-population")
    _exclusion(learning, base["dataset"], learning_groups,
               overlay["population_id"])
    return [discovery, learning]


def _upstreams(tmp_path, base, freeze_run):
    with ResearchRun(tmp_path / "m4", allowed_root=tmp_path,
                     stage="sample-efficiency-batch", dataset=base["dataset"],
                     protocol=base.to_dict()):
        pass
    batch = read_run(tmp_path / "m4", dataset=base["dataset"],
                     protocol=base.to_dict(), stages=("sample-efficiency-batch",))
    with ResearchRun(tmp_path / "m5", allowed_root=tmp_path,
                     stage="sample-efficiency-report", dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=[batch]):
        pass
    report = read_run(tmp_path / "m5", dataset=base["dataset"],
                      protocol=base.to_dict(), stages=("sample-efficiency-report",))
    return [freeze_run, batch, report]


def _resign_json(run_path, filename, value):
    payload_path = run_path / filename
    payload_path.write_bytes(canonical(value) + b"\n")
    manifest_path = run_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][filename] = {
        "sha256": sha256_file(payload_path),
        "size_bytes": payload_path.stat().st_size,
    }
    manifest["artifact_id"] = digest_json({
        key: value for key, value in manifest.items() if key != "artifact_id"
    })
    manifest_path.write_bytes(canonical(manifest) + b"\n")


def test_nonindependent_identity_rejected_before_payload_decode_and_claim(tmp_path, monkeypatch):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(freeze_run.read_json("freeze.json"), base_protocol=base)
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.01] * 20)
    excluded = _required_exclusions(
        tmp_path, base, overlay, discovery_groups=("confirm-a",))
    monkeypatch.setattr(confirmation, "_validate_payload",
                        lambda *args, **kwargs: pytest.fail("payload decoded before independence refusal"))
    with pytest.raises(ResearchError, match="overlaps excluded lineage") as caught:
        confirmation.publish_confirmation(tmp_path / "attempt", allowed_root=tmp_path,
            input_path=package, exclusion_identity_sets=excluded, base=base, overlay=overlay,
            freeze=freeze, freeze_artifact_id=freeze_run.manifest["artifact_id"],
            upstreams=_upstreams(tmp_path, base, freeze_run))
    assert caught.value.status == "confirmation_population_not_independent"
    assert not (tmp_path / ".sample-efficiency-confirmation-claims").exists()


def test_claim_exists_before_decode_and_linear_ci_rule_is_synthetic_only(tmp_path, monkeypatch):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(freeze_run.read_json("freeze.json"), base_protocol=base)
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.05] * 20)
    excluded = _required_exclusions(tmp_path, base, overlay)
    original = confirmation._validate_payload
    def guarded(*args, **kwargs):
        assert list((tmp_path / ".sample-efficiency-confirmation-claims").glob("*.json"))
        return original(*args, **kwargs)
    monkeypatch.setattr(confirmation, "_validate_payload", guarded)
    _, result = confirmation.publish_confirmation(tmp_path / "attempt", allowed_root=tmp_path,
        input_path=package, exclusion_identity_sets=excluded, base=base, overlay=overlay,
        freeze=freeze, freeze_artifact_id=freeze_run.manifest["artifact_id"],
        upstreams=_upstreams(tmp_path, base, freeze_run))
    assert result["upper_ci"] == 0.05
    assert result["status"] == "synthetic_rule_satisfied"
    assert result["status"] != "confirmed_noninferior_within_registered_margin"


def test_identical_claim_requires_explicit_repeat_and_new_attempt(tmp_path):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(freeze_run.read_json("freeze.json"), base_protocol=base)
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.2] * 20)
    excluded = _required_exclusions(tmp_path, base, overlay)
    kwargs = dict(allowed_root=tmp_path, input_path=package, exclusion_identity_sets=excluded,
        base=base, overlay=overlay, freeze=freeze,
        freeze_artifact_id=freeze_run.manifest["artifact_id"],
        upstreams=_upstreams(tmp_path, base, freeze_run))
    _, first = confirmation.publish_confirmation(tmp_path / "first", **kwargs)
    assert first["status"] == "synthetic_rule_not_satisfied"
    with pytest.raises(ResearchStateError) as caught:
        confirmation.publish_confirmation(tmp_path / "second", **kwargs)
    assert caught.value.status == "assessment_already_started"
    _, repeated = confirmation.publish_confirmation(tmp_path / "third", repeat=True, **kwargs)
    assert repeated["claim_key"] == first["claim_key"]
    assert repeated["attempt_id"] != first["attempt_id"]


@pytest.mark.parametrize("mutation", ["extra_delimiter", "extra_payload"])
def test_invalid_payload_line_structure_is_rejected_before_claim(tmp_path, mutation):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(
        freeze_run.read_json("freeze.json"), base_protocol=base,
    )
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.01] * 20)
    content = package.read_bytes()
    if mutation == "extra_delimiter":
        content = content.replace(b"--PAYLOAD--\n", b"--PAYLOAD--\n--PAYLOAD--\n")
    else:
        content += b"{}\n"
    package.write_bytes(content)
    with pytest.raises(ResearchError, match="input grammar"):
        confirmation.publish_confirmation(
            tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
            exclusion_identity_sets=_required_exclusions(tmp_path, base, overlay),
            base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_run.manifest["artifact_id"],
            upstreams=_upstreams(tmp_path, base, freeze_run),
        )
    claim_dir = tmp_path / ".sample-efficiency-confirmation-claims"
    assert not claim_dir.exists()


def test_missing_exclusion_population_is_rejected_before_claim(tmp_path, monkeypatch):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(
        freeze_run.read_json("freeze.json"), base_protocol=base,
    )
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.01] * 20)
    excluded = tmp_path / "excluded-discovery.json"
    _exclusion(excluded, base["dataset"], ["old-a"], "synthetic-discovery-population")
    monkeypatch.setattr(
        confirmation, "_validate_payload",
        lambda *args, **kwargs: pytest.fail("payload decoded before exclusion refusal"),
    )
    with pytest.raises(ResearchError, match="exactly cover") as caught:
        confirmation.publish_confirmation(
            tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
            exclusion_identity_sets=[excluded], base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_run.manifest["artifact_id"],
            upstreams=_upstreams(tmp_path, base, freeze_run),
        )
    assert caught.value.status == "confirmation_population_not_independent"
    assert not (tmp_path / ".sample-efficiency-confirmation-claims").exists()


def test_typed_evaluation_receipt_substitution_is_rejected(tmp_path):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(
        freeze_run.read_json("freeze.json"), base_protocol=base,
    )
    package = tmp_path / "evaluation.pkg"
    _package(
        package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.01] * 20,
        mutate_receipts=lambda receipts: receipts[0].update(role="reference_model"),
    )
    with pytest.raises(ResearchError, match="evaluation package receipts"):
        confirmation.publish_confirmation(
            tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
            exclusion_identity_sets=_required_exclusions(tmp_path, base, overlay),
            base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_run.manifest["artifact_id"],
            upstreams=_upstreams(tmp_path, base, freeze_run),
        )


def test_controlled_mc_remains_external_pending(tmp_path):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(
        freeze_run.read_json("freeze.json"), base_protocol=base,
    )
    package = tmp_path / "evaluation.pkg"
    _package(
        package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.01] * 20,
        source_kind="controlled_mc",
    )
    _, result = confirmation.publish_confirmation(
        tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
        exclusion_identity_sets=_required_exclusions(tmp_path, base, overlay),
        base=base, overlay=overlay, freeze=freeze,
        freeze_artifact_id=freeze_run.manifest["artifact_id"],
        upstreams=_upstreams(tmp_path, base, freeze_run),
    )
    assert result["rule_satisfied"] is True
    assert result["validation_scope"] == "controlled_mc_external_pending"
    assert result["status"] == "external_pending"


def test_reader_replays_claim_input_and_ci_against_self_resigned_tamper(tmp_path):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(
        freeze_run.read_json("freeze.json"), base_protocol=base,
    )
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.2] * 20)
    exclusions = _required_exclusions(tmp_path, base, overlay)
    upstreams = _upstreams(tmp_path, base, freeze_run)
    confirmation.publish_confirmation(
        tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
        exclusion_identity_sets=exclusions, base=base, overlay=overlay, freeze=freeze,
        freeze_artifact_id=freeze_run.manifest["artifact_id"], upstreams=upstreams,
    )
    result_path = tmp_path / "attempt" / "confirmation.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["status"] = "confirmed_noninferior_within_registered_margin"
    result["confirmation_id"] = digest_json({
        key: value for key, value in result.items() if key != "confirmation_id"
    })
    _resign_json(tmp_path / "attempt", "confirmation.json", result)
    with pytest.raises(ResearchError, match="semantic replay"):
        confirmation.read_confirmation(
            tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
            exclusion_identity_sets=exclusions, base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_run.manifest["artifact_id"], upstreams=upstreams,
        )


def test_reader_rejects_claim_field_drift(tmp_path):
    base, _, freeze_run, overlay, _ = build_sample_efficiency_fixture(tmp_path)
    freeze = confirmation.CompactCandidateFreeze(
        freeze_run.read_json("freeze.json"), base_protocol=base,
    )
    package = tmp_path / "evaluation.pkg"
    _package(package, base, overlay, freeze, freeze_run.manifest["artifact_id"], [0.05] * 20)
    exclusions = _required_exclusions(tmp_path, base, overlay)
    upstreams = _upstreams(tmp_path, base, freeze_run)
    _, result = confirmation.publish_confirmation(
        tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
        exclusion_identity_sets=exclusions, base=base, overlay=overlay, freeze=freeze,
        freeze_artifact_id=freeze_run.manifest["artifact_id"], upstreams=upstreams,
    )
    claim_path = tmp_path / ".sample-efficiency-confirmation-claims" / f"{result['claim_key']}.json"
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["unexpected"] = "drift"
    claim_path.write_bytes(canonical(claim) + b"\n")
    with pytest.raises(ResearchError, match="claim receipt mismatch"):
        confirmation.read_confirmation(
            tmp_path / "attempt", allowed_root=tmp_path, input_path=package,
            exclusion_identity_sets=exclusions, base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_run.manifest["artifact_id"], upstreams=upstreams,
        )
