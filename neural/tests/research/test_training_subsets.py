import copy
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from src.research.artifacts import LoadedRun, ResearchRun, read_run
from src.research.data import IDENTITY, role_for_group, write_research_data
from src.research.errors import ResearchError
from src.research.protocol import canonical, load_protocol
from src.research.sample_efficiency_protocol import (
    CompactCandidateFreeze,
    SampleEfficiencyProtocol,
    freeze_compact_candidate,
    load_compact_candidate_freeze,
)
from src.research.training_subsets import (
    _read_train_rows,
    build_training_subset_payloads,
    publish_training_subsets,
    read_training_subsets,
)


def _train_groups(protocol, count=24):
    groups = []
    index = 0
    while len(groups) < count:
        name = f"synthetic-group-{index}"
        if role_for_group(name, protocol.to_dict()) == "train":
            groups.append(name)
        index += 1
    return groups


def _prepared(tmp_path, protocol, *, poison_nontrain=False, order_seed=None):
    groups = _train_groups(protocol)
    rows = []
    for index, group in enumerate(groups):
        for duplicate in range(1 + (index % 2)):
            rows.append({"event_id": f"e:{index}:{duplicate}", "source_row_id": f"r:{index}:{duplicate}",
                "event_group_id": group, "split": "development", "dataset": "atlas2020_4lep",
                "label": index % 2, "role": "train", "physical_weight": (-1 if duplicate else 2) * (index + 1),
                "m4l": 106.0 + index, "feature": index})
    # Add poison payloads in every non-train role, with identities still valid.
    for role in ("validation", "calibration", "template", "assessment"):
        index = 0
        while True:
            group = f"synthetic-{role}-{index}"
            if role_for_group(group, protocol.to_dict()) == role:
                rows.append({"event_id": f"{role}:0", "source_row_id": f"{role}:0", "event_group_id": group,
                    "split": "development", "dataset": "atlas2020_4lep", "label": 0, "role": role,
                    "physical_weight": 1.0, "m4l": 125.0, "feature": 0})
                break
            index += 1
    frame = pd.DataFrame(rows)
    if order_seed is not None:
        frame = frame.sample(frac=1, random_state=order_seed).reset_index(drop=True)
    frame.attrs["source_kind"] = "synthetic"
    root = tmp_path / f"prepared-{order_seed}"
    with ResearchRun(root, allowed_root=tmp_path, stage="prepare", dataset=protocol["dataset"], protocol=protocol.to_dict()) as run:
        receipt = write_research_data(frame, run.path / "events.jsonl", protocol)
        run.register_streamed_file("events.jsonl", sha256=receipt.sha256, size_bytes=receipt.size_bytes)
        run.manifest["context"]["population_id"] = receipt.population_id
    if poison_nontrain:
        # Tampering must happen before receipt publication to remain a valid prepared fixture.
        raise AssertionError("use _poison_prepared")
    return read_run(root, dataset=protocol["dataset"], protocol=protocol.to_dict()), receipt.population_id


def _poison_prepared(tmp_path, protocol):
    prepared, population = _prepared(tmp_path, protocol)
    source = prepared.file("events.jsonl")
    lines = source.read_text().splitlines()
    for i in range(1, len(lines)):
        identity, payload = lines[i].split("\t", 1)
        if json.loads(identity)["role"] != "train":
            lines[i] = identity + "\tPOISON"
    # Publish a second valid run whose receipt binds the poisoned bytes.
    root = tmp_path / "poisoned"
    with ResearchRun(root, allowed_root=tmp_path, stage="prepare", dataset=protocol["dataset"], protocol=protocol.to_dict()) as run:
        target = run.path / "events.jsonl"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        run.register_file("events.jsonl")
        run.manifest["context"]["population_id"] = population
    return read_run(root, dataset=protocol["dataset"], protocol=protocol.to_dict()), population


def _bindings(tmp_path, *, poison=False, order_seed=None, draws=(100, 101), fractions=(0.25, 0.5, 1.0)):
    base = load_protocol()
    prepared, population = (_poison_prepared(tmp_path, base) if poison else _prepared(tmp_path, base, order_seed=order_seed))
    meta = {"discovery_prepared_artifact_ids":["discovery"], "discovery_report_artifact_ids":["report"],
        "selection_artifact_ids":["report"], "discovery_population_ids":["discovery-pop"],
        "browsed_population_ids":["discovery-pop"], "excluded_population_ids":["discovery-pop"],
        "selection_rule_version":"synthetic-v1", "selection_reason":"synthetic test only",
        "evidence_status":"exploratory_only", "delta_w68":0.1, "delta_source":"synthetic-test-only"}
    freeze = freeze_compact_candidate(meta, groups=["A","B"], base_protocol=base)
    freeze_root = tmp_path / "freeze"
    with ResearchRun(freeze_root, allowed_root=tmp_path, stage="compact-freeze", dataset=base["dataset"], protocol=base.to_dict()) as run:
        run.write_json("freeze.json", freeze.to_dict())
    freeze_run = read_run(freeze_root, dataset=base["dataset"], protocol=base.to_dict())
    raw = json.loads((Path(__file__).resolve().parents[2] / "config/research_sample_efficiency_protocol_v1.json").read_text())
    raw.update(protocol_id="synthetic-m2", base_research_protocol_sha256=base.digest,
        prepared_artifact_id=prepared.manifest["artifact_id"], population_id=population,
        compact_candidate_freeze_artifact_id=freeze_run.manifest["artifact_id"],
        compact_candidate_freeze_sha256=freeze.digest,
        representations=["decay7","compact:AB","engineered19"], sample_fractions=list(fractions),
        sample_draw_seeds=list(draws))
    raw["subset_algorithm"].update(min_groups_per_label=1, min_effective_count=1.0)
    raw["noninferiority"].update(delta_w68=0.1, delta_source="synthetic-test-only", confidence_level=0.95,
        bootstrap_replicates=20, bootstrap_seed=300)
    raw["evaluation_uncertainty"].update(replicates=20, seed=200)
    raw["capacity_control"].update(enabled=False, sample_fractions=[], network_seeds=[])
    raw["cdf_check"].update(enabled=False, representations=raw["representations"], sample_fractions=[])
    raw["quality_target"].update(enabled=False)
    overlay = SampleEfficiencyProtocol(raw, base_protocol=base, prepared_artifact_id=prepared.manifest["artifact_id"],
        population_id=population, compact_freeze=freeze, compact_freeze_artifact_id=freeze_run.manifest["artifact_id"])
    return base, prepared, freeze_run, overlay


def _republish_prepared(tmp_path, base, prepared, name, transform):
    lines = prepared.file("events.jsonl").read_text(encoding="utf-8").splitlines()
    transform(lines)
    root = tmp_path / name
    with ResearchRun(root, allowed_root=tmp_path, stage="prepare", dataset=base["dataset"], protocol=base.to_dict()) as run:
        path = run.path / "events.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        run.register_file("events.jsonl")
    return read_run(root, dataset=base["dataset"], protocol=base.to_dict(), stages=("prepare",))


def _rebind_overlay(base, prepared, freeze_run, overlay):
    raw = overlay.to_dict()
    raw["prepared_artifact_id"] = prepared.manifest["artifact_id"]
    freeze = load_compact_candidate_freeze(freeze_run.file("freeze.json"), base_protocol=base)
    return SampleEfficiencyProtocol(raw, base_protocol=base,
        prepared_artifact_id=prepared.manifest["artifact_id"], population_id=raw["population_id"],
        compact_freeze=freeze, compact_freeze_artifact_id=freeze_run.manifest["artifact_id"])


def _publish_subset_fixture(tmp_path, name, base, prepared, freeze_run, overlay, *,
                            plan_transform=lambda value: value, ledger_transform=lambda value: value,
                            overlay_transform=lambda value: value, noncanonical_membership=False):
    plan, members, ledger = build_training_subset_payloads(prepared, base, overlay)
    root = tmp_path / name
    with ResearchRun(root, allowed_root=tmp_path, stage="training-subsets", dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=[prepared, freeze_run],
                     context={"sample_efficiency_protocol_sha256": overlay.digest}) as run:
        run.write_json("sample-efficiency-protocol.json", overlay_transform(copy.deepcopy(overlay.to_dict())))
        run.write_json("training-subsets.json", plan_transform(copy.deepcopy(plan)))
        member_path = run.path / "training-subset-membership.jsonl"
        with member_path.open("x", encoding="utf-8", newline="\n") as stream:
            values = [{"schema_version": "h4l-training-subset-membership-v1"}, *members]
            for value in values:
                text = json.dumps(value, ensure_ascii=False) if noncanonical_membership else canonical(value).decode()
                stream.write(text + "\n")
        run.register_file(member_path.name)
        run.write_json("training-subset-ledger.json", ledger_transform(copy.deepcopy(ledger)))
    return read_run(root, dataset=base["dataset"], protocol=base.to_dict(), stages=("training-subsets",))


def test_deterministic_nested_stratified_full_canonical_and_group_rows(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path)
    plan, members, ledger = build_training_subset_payloads(prepared, base, overlay)
    assert len(plan["subsets"]) == 5  # 2 draws * 2 partial + one canonical full
    full = [x for x in plan["subsets"] if x["draw_or_full"] == "full"]
    assert len(full) == 1
    assert len([x for x in ledger["cells"] if x["fraction"] == 1.0]) == 2
    assert len({x["subset_id"] for x in ledger["cells"] if x["fraction"] == 1.0}) == 1
    for draw in overlay["sample_draw_seeds"]:
        sets = {}
        for fraction in overlay["sample_fractions"]:
            alias = next(x for x in ledger["cells"] if x["sample_draw_seed"] == draw and x["fraction"] == fraction)
            sets[fraction] = {x["event_group_id"] for x in members if x["fraction"] == fraction and
                x["draw_or_full"] == ("full" if fraction == 1 else draw)}
            assert alias["status"] == "planned"
        assert sets[0.25] < sets[0.5] < sets[1.0]
    assert all({x["label"] for x in members if x["draw_or_full"] == draw and x["fraction"] == .25} == {0,1}
               for draw in overlay["sample_draw_seeds"])
    # Repeated computation is byte-equivalent and summary group weights include every source row.
    assert (plan, members, ledger) == build_training_subset_payloads(prepared, base, overlay)
    full_summary = {x["label"]: x for x in full[0]["summary_by_label"]}
    assert sum(x["row_count"] for x in full_summary.values()) > sum(x["group_count"] for x in full_summary.values())
    total = full[0]["summary_total"]
    assert total == {"group_count": 24, "row_count": 36, "sum_signed_weight": 444.0,
        "sum_abs_weight": 444.0, "sumw2": 11800.0, "neff_abs": 444.0**2 / 11800.0,
        "m4l_min": 106.0, "m4l_max": 129.0}
    assert total["group_count"] == sum(item["group_count"] for item in full_summary.values())
    for cell in ledger["cells"]:
        expected = hashlib.sha256(canonical([cell["subset_id"], cell["sample_draw_seed"], cell["fraction"]])).hexdigest()
        assert cell["alias_id"] == expected and type(cell["fraction"]) is float


def test_nontrain_payload_is_never_decoded_and_publish_reader_roundtrip(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path, poison=True)
    output = publish_training_subsets(tmp_path / "subsets", allowed_root=tmp_path, prepared=prepared,
        freeze_run=freeze_run, base=base, overlay=overlay)
    plan, members, ledger = read_training_subsets(output, prepared=prepared, freeze_run=freeze_run, base=base, overlay=overlay)
    assert plan["schema_version"] == "h4l-training-subset-plan-v1"
    assert members and ledger["cells"]
    assert {x["stage"] for x in output.manifest["upstreams"]} == {"prepare", "compact-freeze"}


def test_membership_changes_with_draw_and_is_repeatable(tmp_path):
    base, prepared, _, overlay = _bindings(tmp_path)
    first = build_training_subset_payloads(prepared, base, overlay)[1]
    second = build_training_subset_payloads(prepared, base, overlay)[1]
    assert first == second
    chosen = lambda draw: {x["event_group_id"] for x in first if x["draw_or_full"] == draw and x["fraction"] == .25}
    assert chosen(100) != chosen(101)


def test_identity_digest_and_train_statistics_ignore_input_row_order(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    base, first, _, _ = _bindings(tmp_path / "one", order_seed=1)
    _, second, _, _ = _bindings(tmp_path / "two", order_seed=2)
    assert _read_train_rows(first, base) == _read_train_rows(second, base)


def test_low_statistics_is_retained_without_redraw(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path, fractions=(0.01, 1.0))
    plan, _, ledger = build_training_subset_payloads(prepared, base, overlay)
    low = [x for x in ledger["cells"] if x["fraction"] == .01]
    assert low and all(x["status"] == "training_subset_insufficient_statistics" for x in low)
    output = publish_training_subsets(tmp_path / "low", allowed_root=tmp_path, prepared=prepared,
        freeze_run=freeze_run, base=base, overlay=overlay)
    assert output.manifest["status"] == "complete"


def test_reader_rejects_receipt_and_semantic_tampering(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path)
    output = publish_training_subsets(tmp_path / "subsets", allowed_root=tmp_path, prepared=prepared,
        freeze_run=freeze_run, base=base, overlay=overlay)
    path = output.path / "training-subsets.json"
    value = json.loads(path.read_text()); value["identity_digest"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ResearchError, match="digest"):
        read_training_subsets(output, prepared=prepared, freeze_run=freeze_run, base=base, overlay=overlay)


@pytest.mark.parametrize("kind", ["wrong_split", "duplicate_event_id", "payload_identity_override",
                                  "mixed_group_label", "role_hash_mismatch"])
def test_valid_receipt_prepared_semantic_conflicts_are_rejected(tmp_path, kind):
    base, prepared, freeze_run, overlay = _bindings(tmp_path)

    def transform(lines):
        parsed = []
        for index in range(1, len(lines)):
            identity_text, payload_text = lines[index].split("\t", 1)
            parsed.append((index, json.loads(identity_text), json.loads(payload_text)))
        train = [item for item in parsed if item[1]["role"] == "train"]
        line_index, identity, payload = train[0]
        if kind == "wrong_split":
            identity["split"] = "exploratory"
        elif kind == "duplicate_event_id":
            line_index, identity, payload = train[1]
            identity["event_id"] = train[0][1]["event_id"]
        elif kind == "payload_identity_override":
            payload["event_id"] = identity["event_id"]
        elif kind == "mixed_group_label":
            groups = [item[1]["event_group_id"] for item in train]
            duplicate_group = next(group for group in groups if groups.count(group) > 1)
            line_index, identity, payload = [item for item in train if item[1]["event_group_id"] == duplicate_group][1]
            identity["label"] = 1 - identity["label"]
        else:
            identity["role"] = "validation"
        lines[line_index] = canonical(identity).decode() + "\t" + canonical(payload).decode()

    bad = _republish_prepared(tmp_path, base, prepared, "bad-" + kind, transform)
    rebound = _rebind_overlay(base, bad, freeze_run, overlay)
    with pytest.raises(ResearchError) as error:
        build_training_subset_payloads(bad, base, rebound)
    assert error.value.status == "training_subset_binding_mismatch"


def test_reader_rejects_valid_receipt_noncanonical_membership_and_semantic_payloads(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path)
    noncanonical = _publish_subset_fixture(tmp_path, "noncanonical", base, prepared, freeze_run, overlay,
                                            noncanonical_membership=True)
    with pytest.raises(ResearchError) as error:
        read_training_subsets(noncanonical, prepared=prepared, freeze_run=freeze_run, base=base, overlay=overlay)
    assert error.value.status == "training_subset_binding_mismatch"

    def alter_plan(value):
        value["subsets"][0]["summary_total"]["row_count"] += 1
        return value

    semantic = _publish_subset_fixture(tmp_path, "semantic", base, prepared, freeze_run, overlay,
                                        plan_transform=alter_plan)
    with pytest.raises(ResearchError) as error:
        read_training_subsets(semantic, prepared=prepared, freeze_run=freeze_run, base=base, overlay=overlay)
    assert error.value.status == "training_subset_binding_mismatch"


def test_public_api_reloads_loaded_run_manifest_from_disk(tmp_path):
    base, prepared, _, overlay = _bindings(tmp_path)
    copied = tmp_path / "forged-prepared"
    shutil.copytree(prepared.path, copied)
    manifest_path = copied / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_id"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    forged = LoadedRun(copied, copy.deepcopy(prepared.manifest))
    with pytest.raises(ResearchError) as error:
        build_training_subset_payloads(forged, base, overlay)
    assert error.value.status == "training_subset_binding_mismatch"


def test_publish_rejects_duplicate_key_freeze_with_valid_receipt(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path)
    raw = freeze_run.file("freeze.json").read_text(encoding="utf-8")
    duplicate = raw.replace('{"base_research_protocol_sha256"', '{"status":"frozen","base_research_protocol_sha256"', 1)
    root = tmp_path / "duplicate-freeze"
    with ResearchRun(root, allowed_root=tmp_path, stage="compact-freeze", dataset=base["dataset"], protocol=base.to_dict()) as run:
        path = run.path / "freeze.json"
        path.write_text(duplicate, encoding="utf-8", newline="\n")
        run.register_file("freeze.json")
    bad = read_run(root, dataset=base["dataset"], protocol=base.to_dict(), stages=("compact-freeze",))
    raw_overlay = overlay.to_dict()
    raw_overlay["compact_candidate_freeze_artifact_id"] = bad.manifest["artifact_id"]
    valid_freeze = load_compact_candidate_freeze(freeze_run.file("freeze.json"), base_protocol=base)
    rebound = SampleEfficiencyProtocol(raw_overlay, base_protocol=base,
        prepared_artifact_id=prepared.manifest["artifact_id"], population_id=raw_overlay["population_id"],
        compact_freeze=valid_freeze, compact_freeze_artifact_id=bad.manifest["artifact_id"])
    with pytest.raises(ResearchError):
        publish_training_subsets(tmp_path / "out", allowed_root=tmp_path, prepared=prepared,
            freeze_run=bad, base=base, overlay=rebound)


def test_train_payload_nonfinite_and_identity_conflict_are_binding_failures(tmp_path):
    base, prepared, freeze_run, overlay = _bindings(tmp_path)
    source = prepared.file("events.jsonl")
    lines = source.read_text().splitlines()
    identity, payload = lines[1].split("\t", 1)
    value = json.loads(payload); value["physical_weight"] = float("nan")
    lines[1] = identity + "\t" + json.dumps(value)
    root = tmp_path / "bad"
    with ResearchRun(root, allowed_root=tmp_path, stage="prepare", dataset=base["dataset"], protocol=base.to_dict()) as run:
        (run.path / "events.jsonl").write_text("\n".join(lines) + "\n")
        run.register_file("events.jsonl")
    bad = read_run(root, dataset=base["dataset"], protocol=base.to_dict())
    raw = overlay.to_dict(); raw["prepared_artifact_id"] = bad.manifest["artifact_id"]
    freeze = CompactCandidateFreeze(freeze_run.read_json("freeze.json"), base_protocol=base)
    rebound = SampleEfficiencyProtocol(raw, base_protocol=base, prepared_artifact_id=bad.manifest["artifact_id"],
        population_id=raw["population_id"], compact_freeze=freeze,
        compact_freeze_artifact_id=freeze_run.manifest["artifact_id"])
    with pytest.raises(ResearchError) as error:
        build_training_subset_payloads(bad, base, rebound)
    assert error.value.status == "training_subset_binding_mismatch"
