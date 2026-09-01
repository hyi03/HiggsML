from __future__ import annotations

from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT / "config/angular5_mc_dsid363490_r3_arm64.yaml"


def test_r3_config_is_sealed_to_identity_receipts_and_mc_only() -> None:
    from src.angular5_enrichment_r3_arm64_run import load_angular5_r3_arm64_config

    config = load_angular5_r3_arm64_config(CONFIG)

    assert config.output_run == "runs/angular5-mc-363490-2026-08-26-r3-arm64"
    assert config.authoritative_identity["manifest_sha256"] == (
        "74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0"
    )
    assert config.authoritative_identity["table_sha256"] == (
        "a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94"
    )
    assert tuple(config.artifacts) == (
        "config.yaml",
        "processed/mc_events_angular5.csv.gz",
        "artifacts/identity_validation.json",
        "artifacts/angular5_summary.json",
        "artifacts/run_manifest.json",
    )
    assert "data" not in "\n".join(config.authoritative_identity).lower()


def test_r3_source_identity_is_the_only_join_key() -> None:
    from src.angular5_enrichment_r3_arm64 import SOURCE_IDENTITY

    assert SOURCE_IDENTITY == ("source_sample", "source_entry")
