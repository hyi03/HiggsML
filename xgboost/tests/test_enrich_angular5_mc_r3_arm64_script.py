from __future__ import annotations

import pytest
from pathlib import Path

from src.angular5_enrichment_run import Angular5OutputLayout


def test_r3_cli_exposes_only_sealed_config_and_run_dir() -> None:
    from scripts import enrich_angular5_mc_r3_arm64 as script

    with pytest.raises(SystemExit):
        script.main(
            [
                "--config",
                "sealed.yaml",
                "--run-dir",
                "sealed-run",
                "--data",
                "forbidden.root",
            ]
        )


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(7)])
def test_r3_cli_records_terminal_failure_after_claim(tmp_path, monkeypatch, interrupt) -> None:
    from scripts import enrich_angular5_mc_r3_arm64 as script

    run = tmp_path / "run"
    processed = run / "processed"
    artifacts = run / "artifacts"
    processed.mkdir(parents=True)
    artifacts.mkdir()
    identity = lambda path: (path.stat().st_dev, path.stat().st_ino)
    layout = Angular5OutputLayout(
        run, run / "config.yaml", processed, artifacts,
        {".": identity(run), "processed": identity(processed), "artifacts": identity(artifacts)},
    )
    monkeypatch.setattr(script, "resolve_angular5_r3_arm64_sources", lambda **_: object())
    monkeypatch.setattr(script, "claim_angular5_r3_arm64_output", lambda **_: layout)
    monkeypatch.setattr(script, "enrich_angular5_r3_arm64_mc", lambda _: (_ for _ in ()).throw(interrupt))

    with pytest.raises(type(interrupt)):
        script.main(["--config", "sealed.yaml", "--run-dir", "sealed-run"])

    assert (run / ".terminal.failed").is_dir()
    assert (run / "failure.json").is_file()
