from __future__ import annotations

import csv
from copy import deepcopy
import gzip
import hashlib
import json
import math
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import run_mass_bin_reweighting
import src.full_training_model as full_training_model
from src.features import FEATURES
from src.full_training_policy import load_training_policy
from src.mass_bin_reweighting import ReweightingPolicy
from src.mass_bin_reweighting_run import (
    ReweightingSources,
    StudySource,
    approved_reweighting_artifacts,
    load_mass_bin_reweighting_config,
)


DROP_TOP4 = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)
ANGULAR5_R3_ARM64 = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
    "cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes",
    "phi_production_plane",
)


def test_cli_module_exposes_main():
    assert callable(run_mass_bin_reweighting.main)


@pytest.mark.parametrize(
    ("status", "selected", "expected"),
    [
        ("no_eligible_iteration", False, False),
        ("insufficient_bin_statistics", False, False),
        ("test_nonreproduction", True, True),
    ],
)
def test_cli_sealed_order_and_single_postclaim_parse(monkeypatch, status, selected, expected):
    stages: list[str] = []
    resolver_calls: list[dict] = []
    unresolved = SimpleNamespace(run_dir="out", directory_identities=None)
    claimed = SimpleNamespace(run_dir="out", directory_identities={".": (1, 2)})
    config_path = Path("config/mass_bin_reweighting.yaml")
    config = load_mass_bin_reweighting_config(config_path)
    sources = ReweightingSources(
        training_input=SimpleNamespace(input_run="input", expected_rows=3),
        reference_run="reference",
        ablation_run="ablation",
        raw_zz_path="raw-zz",
        policy="training-policy",
        reweighting_policy="reweighting-policy",
        config=config,
        config_bytes=config_path.read_bytes(),
        records={"study_config": SimpleNamespace(path="cfg")},
    )
    outcome = SimpleNamespace(
        status=status,
        selected_iteration=0 if selected else None,
        model=object() if selected else None,
        test_scores=pd.DataFrame({"score": [0.5]}) if selected else None,
    )
    resolves = iter((unresolved, unresolved))
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_output", lambda **kw: resolver_calls.append(kw) or stages.append("output_preflight" if not stages else "output_rebind") or next(resolves))
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_sources", lambda **kw: stages.append("source_bind_without_csv_parse") or sources)
    monkeypatch.setattr(run_mass_bin_reweighting, "claim_reweighting_output", lambda value: stages.append("atomic_claim") or claimed)
    reads = []
    monkeypatch.setattr(run_mass_bin_reweighting, "load_training_mc_frame", lambda value: reads.append(value) or stages.append("single_mc_parse") or pd.DataFrame({"split": ["train", "validation", "test"]}))
    monkeypatch.setattr(run_mass_bin_reweighting, "summarize_mc_source_rows", lambda frame, expected: {"row_count": 3, "rows_by_split": {"train": 1, "validation": 1, "test": 1}})
    monkeypatch.setattr(run_mass_bin_reweighting, "run_mass_bin_reweighting_study", lambda *a, **kw: stages.append("development_iteration") or outcome)
    monkeypatch.setattr(run_mass_bin_reweighting, "build_reweighting_artifacts", lambda value: stages.append("final_fit_and_test_score") if selected else None or {"selection": {"status": status, "selected_iteration": 0 if selected else None, "test_opened": selected}})
    if selected:
        monkeypatch.setattr(run_mass_bin_reweighting, "build_reweighting_artifacts", lambda value: stages.append("final_fit_and_test_score") or {"selection": {"status": status, "selected_iteration": 0, "test_opened": True}})
    monkeypatch.setattr(run_mass_bin_reweighting, "write_reweighting_artifacts", lambda *a, **kw: stages.append("write_conditional_artifacts") or object())
    monkeypatch.setattr(run_mass_bin_reweighting, "assert_reweighting_sources_unchanged", lambda value: stages.append("source_recheck"))
    monkeypatch.setattr(run_mass_bin_reweighting, "publish_reweighting_manifest", lambda *a, **kw: stages.append("publish_manifest_last") or {})
    monkeypatch.setattr(run_mass_bin_reweighting, "policy_manifest_record", lambda value: {"policy": value})
    monkeypatch.setattr(run_mass_bin_reweighting, "software_versions", lambda: {})
    assert run_mass_bin_reweighting.main(["--input-run", "in", "--reference-run", "ref", "--config", "cfg", "--run-dir", "out"]) == 0
    expected_stages = [
        "output_preflight", "source_bind_without_csv_parse", "output_rebind",
        "atomic_claim", "single_mc_parse", "development_iteration",
    ]
    if expected:
        expected_stages.append("final_fit_and_test_score")
    expected_stages += ["write_conditional_artifacts", "source_recheck", "publish_manifest_last"]
    assert stages == expected_stages
    assert len(reads) == 1
    assert resolver_calls[1]["reweighting_reference_run"] is None


def test_drop_top4_cli_uses_exact_profile_and_protects_reference_run(monkeypatch):
    resolver_calls: list[dict] = []
    writer_calls: list[dict] = []
    study_calls: list[dict] = []
    unresolved = SimpleNamespace(run_dir="out", directory_identities=None)
    claimed = SimpleNamespace(run_dir="out", directory_identities={".": (1, 2)})
    config_path = Path("config/mass_bin_reweighting_drop_top4.yaml")
    config = load_mass_bin_reweighting_config(config_path)
    sources = ReweightingSources(
        config=config,
        config_bytes=config_path.read_bytes(),
        training_input=SimpleNamespace(input_run="input", expected_rows=3),
        reference_run=Path("reference"),
        ablation_run=Path("ablation"),
        raw_zz_path=Path("raw-zz"),
        reweighting_reference_run=Path("reweighting-reference"),
        policy="training-policy",
        reweighting_policy="reweighting-policy",
        records={"study_config": SimpleNamespace(path="cfg")},
    )
    parsed_frame = object()
    outcome = SimpleNamespace(
        status="no_eligible_iteration", selected_iteration=None,
        model=None, test_scores=None,
    )
    resolves = iter((unresolved, unresolved))
    monkeypatch.setattr(
        run_mass_bin_reweighting, "resolve_reweighting_output",
        lambda **kwargs: resolver_calls.append(kwargs) or next(resolves),
    )
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_sources", lambda **kwargs: sources)
    monkeypatch.setattr(run_mass_bin_reweighting, "claim_reweighting_output", lambda value: claimed)
    monkeypatch.setattr(run_mass_bin_reweighting, "load_training_mc_frame", lambda value: parsed_frame)
    monkeypatch.setattr(run_mass_bin_reweighting, "summarize_mc_source_rows", lambda *args: {"row_count": 3, "rows_by_split": {"train": 1, "validation": 1, "test": 1}})

    def study(frame, training_policy, reweighting_policy, *, features):
        study_calls.append({
            "frame": frame,
            "training_policy": training_policy,
            "reweighting_policy": reweighting_policy,
            "features": features,
        })
        return outcome

    monkeypatch.setattr(run_mass_bin_reweighting, "run_mass_bin_reweighting_study", study)
    monkeypatch.setattr(run_mass_bin_reweighting, "build_reweighting_artifacts", lambda value: {"selection": {"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False}})
    monkeypatch.setattr(run_mass_bin_reweighting, "write_reweighting_artifacts", lambda *args, **kwargs: writer_calls.append(kwargs) or object())
    monkeypatch.setattr(run_mass_bin_reweighting, "assert_reweighting_sources_unchanged", lambda value: None)
    monkeypatch.setattr(run_mass_bin_reweighting, "publish_reweighting_manifest", lambda *args, **kwargs: {})
    monkeypatch.setattr(run_mass_bin_reweighting, "policy_manifest_record", lambda value: {})
    monkeypatch.setattr(run_mass_bin_reweighting, "software_versions", lambda: {})

    assert run_mass_bin_reweighting.main(["--input-run", "in", "--reference-run", "ref", "--config", "cfg", "--run-dir", "out"]) == 0
    assert study_calls == [{
        "frame": parsed_frame,
        "training_policy": sources.policy,
        "reweighting_policy": sources.reweighting_policy,
        "features": DROP_TOP4,
    }]
    assert resolver_calls[1]["reweighting_reference_run"] == Path("reweighting-reference")
    assert writer_calls[0]["features"] == DROP_TOP4


def test_angular5_r3_arm64_cli_passes_only_the_sealed_15_feature_profile(monkeypatch):
    unresolved = SimpleNamespace(run_dir="out", directory_identities=None)
    claimed = SimpleNamespace(run_dir="out", directory_identities={".": (1, 2)})
    config_path = Path("config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml")
    config = load_mass_bin_reweighting_config(config_path)
    sources = ReweightingSources(
        config=config,
        config_bytes=config_path.read_bytes(),
        training_input=SimpleNamespace(
            input_run="input", expected_rows=3,
            mc_path=Path(config.input_table_path),
        ),
        reference_run=Path("reference"), ablation_run=Path("ablation"),
        raw_zz_path=Path("raw-zz"), reweighting_reference_run=Path("reweighting-reference"),
        policy="training-policy", reweighting_policy="reweighting-policy",
        records={"study_config": SimpleNamespace(path="cfg")},
    )
    calls: list[tuple[str, object]] = []
    resolves = iter((unresolved, unresolved))
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_output", lambda **_: next(resolves))
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_sources", lambda **_: sources)
    monkeypatch.setattr(run_mass_bin_reweighting, "claim_reweighting_output", lambda _: claimed)
    monkeypatch.setattr(run_mass_bin_reweighting, "load_training_mc_frame", lambda value: calls.append(("load", value)) or object())
    monkeypatch.setattr(run_mass_bin_reweighting, "summarize_mc_source_rows", lambda *_: {"row_count": 3, "rows_by_split": {"train": 1, "validation": 1, "test": 1}})
    outcome = SimpleNamespace(status="no_eligible_iteration", selected_iteration=None, model=None, test_scores=None)
    monkeypatch.setattr(run_mass_bin_reweighting, "run_mass_bin_reweighting_study", lambda *_, features: calls.append(("features", features)) or outcome)
    monkeypatch.setattr(run_mass_bin_reweighting, "build_reweighting_artifacts", lambda _: {"selection": {"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False}})
    monkeypatch.setattr(run_mass_bin_reweighting, "write_reweighting_artifacts", lambda *_, **__: object())
    monkeypatch.setattr(run_mass_bin_reweighting, "assert_reweighting_sources_unchanged", lambda _: None)
    monkeypatch.setattr(run_mass_bin_reweighting, "publish_reweighting_manifest", lambda *_, **__: {})
    monkeypatch.setattr(run_mass_bin_reweighting, "policy_manifest_record", lambda _: {})
    monkeypatch.setattr(run_mass_bin_reweighting, "software_versions", lambda: {})

    assert run_mass_bin_reweighting.main(["--input-run", "in", "--reference-run", "ref", "--config", "cfg", "--run-dir", "out"]) == 0
    assert calls == [("load", sources.training_input), ("features", ANGULAR5_R3_ARM64)]


def test_occupied_output_refuses_before_csv_model_or_plot(monkeypatch):
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_output", lambda **kw: (_ for _ in ()).throw(FileExistsError("occupied")))
    monkeypatch.setattr(run_mass_bin_reweighting, "resolve_reweighting_sources", lambda **kw: pytest.fail("sources must stay unopened"))
    monkeypatch.setattr(pd, "read_csv", lambda *a, **kw: pytest.fail("CSV must stay unopened"))
    monkeypatch.setattr(run_mass_bin_reweighting, "run_mass_bin_reweighting_study", lambda *a, **kw: pytest.fail("model must stay unopened"))
    monkeypatch.setattr(run_mass_bin_reweighting, "build_reweighting_artifacts", lambda *a, **kw: pytest.fail("plots must stay unopened"))
    with pytest.raises(FileExistsError, match="occupied"):
        run_mass_bin_reweighting.main(["--input-run", "in", "--reference-run", "ref", "--config", "cfg", "--run-dir", "out"])


def test_insufficient_statistics_builds_only_truthful_common_artifacts():
    outcome = SimpleNamespace(
        status="insufficient_bin_statistics",
        iterations=(),
        selected_iteration=None,
        selected_oof_scores=None,
        model=None,
        test_scores=None,
        test_metrics=None,
    )
    artifacts = run_mass_bin_reweighting.build_reweighting_artifacts(outcome)
    assert artifacts["selection"]["test_opened"] is False
    assert set(artifacts["plot_artifacts"]) == {
        "iteration_tradeoff.png", "zz_efficiency_by_mass.png"
    }
    assert all(payload.startswith(b"\x89PNG\r\n\x1a\n") for payload in artifacts["plot_artifacts"].values())
    assert "model" not in artifacts
    assert "test_metrics" not in artifacts


@pytest.mark.parametrize("selected", [False, True], ids=("no-selection", "selected"))
def test_synthetic_drop_top4_completed_run_publishes_exact_auditable_terminal(
    tmp_path, monkeypatch, selected
):
    """Wrong profile, row cardinality, receipt, or terminal allowlist must fail."""
    frame = _real_xgboost_frame(separated=selected)
    config_path = tmp_path / "config.yaml"
    config_path.write_bytes(Path("config/mass_bin_reweighting_drop_top4.yaml").read_bytes())
    source_path = tmp_path / "source.json"
    source_path.write_text('{"synthetic":true}\n')
    names = {
        "study_config", "task4a_config", "task4a_mc", "task4a_summary",
        "task4a_manifest", "reference_config", "reference_manifest",
        "reference_model", "reference_metrics", "ablation_manifest", "raw_zz",
        "reweighting_reference_manifest",
    }
    records = {
        name: StudySource.from_path(
            name, config_path if name == "study_config" else source_path
        )
        for name in names
    }
    config = load_mass_bin_reweighting_config(config_path)
    sources = ReweightingSources(
        config=config,
        config_bytes=config_path.read_bytes(),
        training_input=SimpleNamespace(input_run=tmp_path / "input", expected_rows=len(frame)),
        reference_run=tmp_path / "reference",
        ablation_run=tmp_path / "ablation",
        raw_zz_path=tmp_path / "raw-zz.root",
        reweighting_reference_run=tmp_path / "reweighting-reference",
        policy=load_training_policy(Path("config/full_training.yaml")),
        reweighting_policy=ReweightingPolicy(
            mass_bin_edges=config.mass_bin_edges,
            minimum_effective_count=config.minimum_effective_count,
            epsilon_floor=config.epsilon_floor,
            damping=config.damping,
            round_factor_bounds=config.round_factor_bounds,
            cumulative_bounds=config.cumulative_bounds,
            maximum_corrections=config.maximum_corrections,
            auc_floor=config.auc_floor,
            ks_limit=config.ks_limit,
        ),
        records=records,
    )
    model_inputs: list[tuple[str, ...]] = []
    poisoned = {"m4l", "lep3_pt", "lep4_pt", "mZ1", "mZ2"}

    class RecordingXGBClassifier:
        def __init__(self, **parameters):
            from xgboost import XGBClassifier

            self._model = XGBClassifier(**parameters)

        def fit(self, values, *args, eval_set=None, **kwargs):
            _record_model_input(values)
            if eval_set is not None:
                for evaluation, _labels in eval_set:
                    _record_model_input(evaluation)
            self._model.fit(values, *args, eval_set=eval_set, **kwargs)
            return self

        def predict_proba(self, values):
            _record_model_input(values)
            return self._model.predict_proba(values)

        def get_booster(self):
            return self._model.get_booster()

        def __getattr__(self, name):
            return getattr(self._model, name)

    def _record_model_input(values):
        columns = tuple(values.columns)
        assert columns == DROP_TOP4
        assert poisoned.isdisjoint(columns)
        model_inputs.append(columns)

    monkeypatch.setattr(
        full_training_model,
        "_default_model_factory",
        lambda **parameters: RecordingXGBClassifier(**parameters),
    )
    monkeypatch.setattr(
        run_mass_bin_reweighting,
        "resolve_reweighting_sources",
        lambda **kwargs: sources,
    )
    monkeypatch.setattr(
        run_mass_bin_reweighting,
        "load_training_mc_frame",
        lambda training_input: frame.copy(deep=True),
    )
    run_dir = tmp_path / "output"
    assert run_mass_bin_reweighting.main(
        [
            "--input-run", str(tmp_path / "input"),
            "--reference-run", str(tmp_path / "reference"),
            "--config", str(config_path),
            "--run-dir", str(run_dir),
        ]
    ) == 0
    selection = pd.read_json(run_dir / "artifacts/selection.json", typ="series")
    manifest = json.loads(
        (run_dir / "artifacts/study_manifest.json").read_text(encoding="utf-8")
    )
    relative_files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }
    assert manifest["policy"]["features"] == list(DROP_TOP4)
    assert manifest["decision"]["test_opened"] is selected
    assert selection["test_opened"] is selected
    _assert_completed_run_manifest(manifest, run_dir, frame, selected=selected)
    _assert_completed_run_oracle_rejects_mutated_evidence(
        manifest, run_dir, frame, selected=selected
    )
    assert relative_files == approved_reweighting_artifacts(selected=selected)

    iterations = pd.read_csv(run_dir / "artifacts/iteration_results.csv")
    bins = pd.read_csv(run_dir / "artifacts/bin_efficiencies.csv")
    multipliers = pd.read_csv(run_dir / "artifacts/weight_multipliers.csv")
    selected_iteration = manifest["decision"]["selected_iteration"]
    expected_iterations = (
        list(range(selected_iteration + 1)) if selected else list(range(6))
    )
    assert iterations["iteration"].tolist() == expected_iterations
    assert bins.groupby("iteration", sort=True).size().to_dict() == {
        iteration: 33 for iteration in expected_iterations
    }
    assert multipliers.groupby("iteration", sort=True).size().to_dict() == {
        iteration: 11 for iteration in expected_iterations
    }
    for name in (
        "iteration_results.csv", "bin_efficiencies.csv", "weight_multipliers.csv"
    ):
        _assert_finite_csv_values(run_dir / "artifacts" / name)
    for path in run_dir.rglob("*.json"):
        _assert_finite_json(json.loads(path.read_text(encoding="utf-8")))

    assert model_inputs
    assert all(columns == DROP_TOP4 for columns in model_inputs)
    if selected:
        metadata = json.loads(
            (run_dir / "model/xgboost_model.json").read_text(encoding="utf-8")
        )
        feature_names = metadata["learner"]["feature_names"]
        assert feature_names == list(DROP_TOP4)
        assert poisoned.isdisjoint(feature_names)
    else:
        assert not (run_dir / "model/xgboost_model.json").exists()


def _assert_finite_json(value) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _assert_finite_json(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def _assert_completed_run_manifest(
    manifest: dict, run_dir: Path, frame: pd.DataFrame, *, selected: bool
) -> None:
    expected_outputs = approved_reweighting_artifacts(selected=selected) - {
        "artifacts/study_manifest.json"
    }
    assert set(manifest["outputs"]) == expected_outputs
    for relative, receipt in manifest["outputs"].items():
        path = run_dir / relative
        payload = path.read_bytes()
        assert receipt["size_bytes"] == len(payload)
        assert receipt["sha256"] == hashlib.sha256(payload).hexdigest()
        if relative.endswith((".csv", ".csv.gz")):
            assert receipt["row_count"] == _independent_csv_row_count(path)

    source = manifest["sources"]["task4a_mc"]
    assert source["row_count"] == len(frame)
    assert source["rows_by_split"] == {
        str(split): int(count)
        for split, count in frame["split"].value_counts(sort=False).items()
    }


def _assert_completed_run_oracle_rejects_mutated_evidence(
    manifest: dict, run_dir: Path, frame: pd.DataFrame, *, selected: bool
) -> None:
    mutations = []

    missing_output = deepcopy(manifest)
    missing_output["outputs"].pop(next(iter(missing_output["outputs"])))
    mutations.append(missing_output)

    wrong_size = deepcopy(manifest)
    first_output = next(iter(wrong_size["outputs"].values()))
    first_output["size_bytes"] += 1
    mutations.append(wrong_size)

    wrong_csv_rows = deepcopy(manifest)
    wrong_csv_rows["outputs"]["artifacts/iteration_results.csv"]["row_count"] += 1
    mutations.append(wrong_csv_rows)

    wrong_source_rows = deepcopy(manifest)
    wrong_source_rows["sources"]["task4a_mc"]["row_count"] += 1
    mutations.append(wrong_source_rows)

    wrong_split_rows = deepcopy(manifest)
    first_split = next(
        iter(wrong_split_rows["sources"]["task4a_mc"]["rows_by_split"])
    )
    wrong_split_rows["sources"]["task4a_mc"]["rows_by_split"][first_split] += 1
    mutations.append(wrong_split_rows)

    for changed in mutations:
        with pytest.raises(AssertionError):
            _assert_completed_run_manifest(changed, run_dir, frame, selected=selected)


def _independent_csv_row_count(path: Path) -> int:
    if path.suffix == ".gz":
        handle = gzip.open(path, mode="rt", newline="", encoding="utf-8")
    else:
        handle = path.open(mode="r", newline="", encoding="utf-8")
    with handle:
        rows = sum(1 for _ in csv.reader(handle))
    assert rows >= 1
    return rows - 1


def _assert_finite_csv_values(path: Path) -> None:
    text_columns = {
        "iteration_results.csv": {"candidate", "eligible", "eligibility_reasons"},
        "bin_efficiencies.csv": {"mass_bin", "working_point"},
        "weight_multipliers.csv": {"mass_bin"},
    }[path.name]
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for name, value in row.items():
                if name not in text_columns:
                    assert value != ""
                    assert math.isfinite(float(value))


def _real_xgboost_frame(*, separated: bool = True) -> pd.DataFrame:
    edges = tuple(float(value) for value in range(105, 161, 5))
    rows = []
    event_number = 0
    for split, count in (("train", 70), ("validation", 30), ("test", 100)):
        for lower, upper in zip(edges, edges[1:]):
            for label in (0, 1):
                for rank in range(count):
                    quantile = (rank + 0.5) / count
                    latent = np.log(quantile / (1.0 - quantile)) + (
                        2.5 if separated and label else 0.0
                    )
                    features = {
                        name: latent + (index % 3) * 0.01
                        for index, name in enumerate(FEATURES)
                    }
                    rows.append(
                        {
                            **features,
                            "m4l": (lower + upper) / 2.0,
                            "eventNumber": event_number,
                            "channelNumber": 345060 if label else 363490,
                            "split": split,
                            "label": label,
                            "physical_weight": 1.0,
                        }
                    )
                    event_number += 1
    return pd.DataFrame(rows)
