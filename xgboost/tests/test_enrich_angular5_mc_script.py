from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_angular5_enrichment import SUCCESS_FILES, _claimed_layout, _fixture_sources


def test_cli_accepts_only_config_and_run_dir_and_publishes_no_data_surface(
    tmp_path, monkeypatch
) -> None:
    from scripts import enrich_angular5_mc as script

    sources, _ = _fixture_sources(tmp_path)
    layout = _claimed_layout(sources)
    calls = []

    def resolve(**kwargs):
        calls.append(("resolve", kwargs))
        return sources

    def claim(**kwargs):
        calls.append(("claim", kwargs))
        return layout

    monkeypatch.setattr(script, "resolve_angular5_sources", resolve)
    monkeypatch.setattr(script, "claim_angular5_output", claim)

    script.main(["--config", "sealed.yaml", "--run-dir", "sealed-run"])

    assert [name for name, _ in calls] == ["resolve", "claim"]
    files = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert files == SUCCESS_FILES
    manifest_text = (layout.artifacts_dir / "run_manifest.json").read_text().lower()
    assert "perioda" not in manifest_text
    assert "data16" not in manifest_text
    assert set(json.loads(manifest_text)["inputs"]) == {
        "enrichment_config",
        "frozen_config",
        "task4a_manifest",
        "task4a_mc",
        "higgs_root",
        "zz_root",
    }

    with pytest.raises(SystemExit):
        script.main(
            [
                "--config",
                "sealed.yaml",
                "--run-dir",
                "sealed-run",
                "--data",
                "data16_periodA.root",
            ]
        )


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(7)])
def test_cli_records_base_exception_failure_only_after_output_claim(
    tmp_path, monkeypatch, interrupt
) -> None:
    from scripts import enrich_angular5_mc as script

    sources, _ = _fixture_sources(tmp_path)
    layout = _claimed_layout(sources)
    monkeypatch.setattr(script, "resolve_angular5_sources", lambda **kwargs: sources)
    monkeypatch.setattr(script, "claim_angular5_output", lambda **kwargs: layout)
    monkeypatch.setattr(
        script,
        "enrich_angular5_mc",
        lambda sources: (_ for _ in ()).throw(interrupt),
    )

    with pytest.raises(type(interrupt)):
        script.main(["--config", "sealed.yaml", "--run-dir", "sealed-run"])

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert json.loads((layout.run_dir / "failure.json").read_text())["status"] == "failed"
    assert not (layout.artifacts_dir / "run_manifest.json").exists()
