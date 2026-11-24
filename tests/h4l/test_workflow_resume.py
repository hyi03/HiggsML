from __future__ import annotations

from pathlib import Path

from higgsml.artifacts import ResearchRun
from higgsml.workflow_resume import classify_stage


DATASET = "atlas2020_4lep"
PROTOCOL = {"schema_version": "test-protocol-v1", "dataset": DATASET}


def test_classify_stage_skips_a_valid_complete_artifact(tmp_path: Path) -> None:
    output_root = tmp_path / "workflow"
    stage = output_root / "train"
    with ResearchRun(
        stage, allowed_root=output_root, stage="train",
        dataset=DATASET, protocol=PROTOCOL,
    ):
        pass

    action = classify_stage(
        stage, allowed_root=output_root, dataset=DATASET,
        protocol=PROTOCOL, stages=("train",),
    )

    assert action == "skip"
    assert stage.is_dir()


def test_classify_stage_quarantines_an_invalid_final_directory(tmp_path: Path) -> None:
    output_root = tmp_path / "workflow"
    stage = output_root / "train"
    stage.mkdir(parents=True)
    (stage / "manifest.json").write_text("not-json", encoding="utf-8")

    action = classify_stage(
        stage, allowed_root=output_root, dataset=DATASET,
        protocol=PROTOCOL, stages=("train",),
    )

    assert action == "retry"
    assert not stage.exists()
    quarantined = list(output_root.glob(".train.*.invalid"))
    assert len(quarantined) == 1
    assert (quarantined[0] / "manifest.json").read_text(encoding="utf-8") == "not-json"


def test_classify_stage_runs_when_the_target_does_not_exist(tmp_path: Path) -> None:
    output_root = tmp_path / "workflow"
    output_root.mkdir()

    assert classify_stage(
        output_root / "train", allowed_root=output_root, dataset=DATASET,
        protocol=PROTOCOL, stages=("train",),
    ) == "run"
