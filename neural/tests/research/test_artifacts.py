import json

import pytest

from src.artifacts.transaction import RunPathError
from src.research.artifacts import ResearchRun, read_run, digest_json
from src.research.errors import ResearchError, ResearchStateError


def test_artifact_binding_and_tampering(tmp_path):
    protocol = {"protocol_id": "synthetic", "dataset": "atlas2020_4lep"}
    with ResearchRun(tmp_path / "first", allowed_root=tmp_path, stage="audit",
                     dataset="atlas2020_4lep", protocol=protocol) as run:
        run.write_json("audit.json", {"count": 12})
    loaded = read_run(tmp_path / "first", dataset="atlas2020_4lep", protocol=protocol)
    assert loaded.read_json("audit.json") == {"count": 12}
    assert loaded.manifest["protocol_sha256"] == digest_json(protocol)
    with pytest.raises(ResearchError, match="dataset"):
        read_run(tmp_path / "first", dataset="atlas2025_exactly4lep", protocol=protocol)
    with pytest.raises(ResearchError, match="protocol"):
        read_run(tmp_path / "first", dataset="atlas2020_4lep", protocol={"other": 1})
    (tmp_path / "first" / "audit.json").write_text('{}', encoding="utf-8")
    with pytest.raises(ResearchError, match="digest"):
        loaded.read_json("audit.json")


def test_upstream_binding_and_no_overwrite(tmp_path):
    protocol = {"protocol_id": "synthetic"}
    with ResearchRun(tmp_path / "one", allowed_root=tmp_path, stage="prepare",
                     dataset="atlas2020_4lep", protocol=protocol) as run:
        run.write_json("data.json", [1])
    upstream = read_run(tmp_path / "one", dataset="atlas2020_4lep", protocol=protocol)
    with ResearchRun(tmp_path / "two", allowed_root=tmp_path, stage="train",
                     dataset="atlas2020_4lep", protocol=protocol, upstreams=[upstream]) as run:
        run.write_json("model.json", {"model": 1})
    child = read_run(tmp_path / "two", dataset="atlas2020_4lep", protocol=protocol)
    assert child.manifest["upstreams"][0]["artifact_id"] == upstream.manifest["artifact_id"]
    with pytest.raises(RunPathError):
        ResearchRun(tmp_path / "one", allowed_root=tmp_path, stage="audit",
                    dataset="atlas2020_4lep", protocol=protocol)


def test_scientific_terminal_state_is_durable_and_not_usable(tmp_path):
    with ResearchRun(tmp_path / "blocked", allowed_root=tmp_path, stage="infer",
                     dataset="atlas2020_4lep", protocol={}) as run:
        raise ResearchStateError("MELA reference absent", status="external_reference_missing")
    receipt = json.loads((tmp_path / "blocked" / "manifest.json").read_text())
    assert receipt["status"] == "external_reference_missing"
    assert receipt["repository_authority_validation"] == "not_run"
    with pytest.raises(ResearchError, match="usable"):
        read_run(tmp_path / "blocked", dataset="atlas2020_4lep", protocol={})


def test_exception_retains_transaction_failure_receipt(tmp_path):
    with pytest.raises(ResearchError):
        with ResearchRun(tmp_path / "failed", allowed_root=tmp_path, stage="train",
                         dataset="atlas2020_4lep", protocol={}) as run:
            raise ResearchError("invalid source")
    assert (tmp_path / "failed" / "failure.json").exists()


def test_reject_traversal_and_symlink_payloads(tmp_path):
    with ResearchRun(tmp_path / "run", allowed_root=tmp_path, stage="audit",
                     dataset="atlas2020_4lep", protocol={}) as run:
        with pytest.raises(ResearchError, match="filename"):
            run.write_json("../outside.json", {})
