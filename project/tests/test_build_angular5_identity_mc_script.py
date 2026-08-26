from __future__ import annotations

import json

import pytest

from test_angular5_identity_run import (
    OUTPUT_RUN,
    R3_OUTPUT_RUN,
    SUCCESS_FILES,
    _fixture_sources,
    _r3_fixture_sources,
)


def test_identity_cli_accepts_only_config_and_run_dir_and_has_no_data_surface(
    tmp_path, monkeypatch
):
    from scripts import build_angular5_identity_mc as script

    sources = _fixture_sources(tmp_path)
    real_claim = script.claim_identity_output
    monkeypatch.setattr(script, "resolve_identity_sources", lambda **kwargs: sources)
    monkeypatch.setattr(
        script,
        "claim_identity_output",
        lambda **kwargs: real_claim(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=OUTPUT_RUN,
        ),
    )

    script.main(["--config", "sealed.yaml", "--run-dir", OUTPUT_RUN])

    run_dir = sources.project_root / OUTPUT_RUN
    files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }
    assert files == SUCCESS_FILES
    manifest_text = (run_dir / "artifacts/run_manifest.json").read_text().lower()
    assert "perioda" not in manifest_text
    assert "data16" not in manifest_text
    assert json.loads(manifest_text)["status"] == "complete"

    with pytest.raises(SystemExit):
        script.main(
            [
                "--config",
                "sealed.yaml",
                "--run-dir",
                OUTPUT_RUN,
                "--data",
                "data16_periodA.root",
            ]
        )


def test_r3_identity_cli_rejects_non_arm64_before_creating_output(
    tmp_path, monkeypatch
):
    from scripts import build_angular5_identity_mc as script
    from src import angular5_identity_run as identity_run

    sources = _r3_fixture_sources(tmp_path)
    real_claim = script.claim_identity_output
    monkeypatch.setattr(script, "resolve_identity_sources", lambda **kwargs: sources)
    monkeypatch.setattr(
        script,
        "claim_identity_output",
        lambda **kwargs: real_claim(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=R3_OUTPUT_RUN,
        ),
    )
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "x86_64")

    with pytest.raises(RuntimeError, match="native arm64"):
        script.main(["--config", "sealed.yaml", "--run-dir", R3_OUTPUT_RUN])

    assert not (sources.project_root / R3_OUTPUT_RUN).exists()


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(7)])
def test_identity_cli_records_control_exception_after_claim(
    tmp_path, monkeypatch, interrupt
):
    from scripts import build_angular5_identity_mc as script

    sources = _fixture_sources(tmp_path)
    real_claim = script.claim_identity_output
    monkeypatch.setattr(script, "resolve_identity_sources", lambda **kwargs: sources)
    monkeypatch.setattr(
        script,
        "claim_identity_output",
        lambda **kwargs: real_claim(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=OUTPUT_RUN,
        ),
    )
    monkeypatch.setattr(
        script, "build_identity_mc", lambda sources: (_ for _ in ()).throw(interrupt)
    )

    with pytest.raises(type(interrupt)):
        script.main(["--config", "sealed.yaml", "--run-dir", OUTPUT_RUN])

    run_dir = sources.project_root / OUTPUT_RUN
    assert (run_dir / ".terminal.failed").is_dir()
    assert json.loads((run_dir / "failure.json").read_text())["status"] == "failed"
    assert not (run_dir / "artifacts/run_manifest.json").exists()
