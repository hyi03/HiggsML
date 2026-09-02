from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import numpy as np

from src.config import load_xgboost_protocol
from src.full_training_policy import (
    class_balanced_training_weights as legacy_weights,
    development_fold as legacy_fold,
)
from src.training import trainer
from src.training.folds import (
    assign_development_folds,
    class_balanced_training_weights,
    development_fold,
)
from src.training.trainer import build_development_evidence, fit_final_model
from tests.refactor_training_support import FakeClassifier, development_frame


PROJECT = Path(__file__).resolve().parents[2]


def test_fold_and_class_balanced_weights_match_legacy_authority_exactly() -> None:
    frame = development_frame()
    assert development_fold(363490, 17, 5) == legacy_fold(363490, 17, 5)
    np.testing.assert_array_equal(
        class_balanced_training_weights(frame), legacy_weights(frame)
    )


def test_hash_folds_cover_every_row_and_each_fold_has_both_labels() -> None:
    frame = development_frame()
    assigned = assign_development_folds(frame, 5)

    assert assigned.index.equals(frame.index)
    assert set(assigned) == set(range(5))
    for fold in range(5):
        assert set(frame.loc[assigned == fold, "label"]) == {0, 1}


def test_new_training_imports_do_not_reach_legacy_execution_modules() -> None:
    targets = [*(PROJECT / "src/training").glob("*.py"), PROJECT / "src/cli/xgboost.py"]
    forbidden = (
        "src.experiment_config", "src.experiment_runner", "src.full_training",
        "src.decorrelation_training", "src.mass_bin_reweighting",
        "src.mass_sculpting_ablation", "src.preprocessing.application",
        "src.preprocessing.reader", "src.train", "src.plots",
    )
    imported: set[str] = set()
    for path in targets:
        module = ".".join(path.relative_to(PROJECT).with_suffix("").parts)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = (
                    importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                    if node.level
                    else node.module or ""
                )
                if base:
                    imported.add(base)
    violations = sorted(
        name for name in imported
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
    )
    assert violations == []


def test_train_weight_is_audit_only_for_oof_and_final_fit() -> None:
    protocol = load_xgboost_protocol(PROJECT / "config/xgboost_protocol_v1.yaml")
    baseline = development_frame()
    baseline["m4l"] = 125.0
    adversarial = baseline.copy()
    adversarial["train_weight"] = np.linspace(-1.0e30, 1.0e30, len(adversarial))
    baseline_models: list[FakeClassifier] = []
    adversarial_models: list[FakeClassifier] = []

    def factory(bucket: list[FakeClassifier]):
        def create(**parameters: object) -> FakeClassifier:
            model = FakeClassifier(**parameters)
            bucket.append(model)
            return model

        return create

    baseline_evidence = build_development_evidence(
        baseline, protocol, model_factory=factory(baseline_models)
    )
    adversarial_evidence = build_development_evidence(
        adversarial, protocol, model_factory=factory(adversarial_models)
    )
    assert baseline_evidence.qualification["eligible"] is True
    assert adversarial_evidence.qualification["eligible"] is True
    fit_final_model(
        baseline,
        protocol,
        baseline_evidence,
        model_factory=factory(baseline_models),
    )
    fit_final_model(
        adversarial,
        protocol,
        adversarial_evidence,
        model_factory=factory(adversarial_models),
    )

    np.testing.assert_array_equal(
        baseline_evidence.oof_frame["oof_score"],
        adversarial_evidence.oof_frame["oof_score"],
    )
    assert len(baseline_models) == len(adversarial_models) == 6
    for baseline_model, adversarial_model in zip(
        baseline_models, adversarial_models, strict=True
    ):
        assert baseline_model.fit_weight is not None
        assert adversarial_model.fit_weight is not None
        np.testing.assert_array_equal(
            baseline_model.fit_weight, adversarial_model.fit_weight
        )


def test_code_hash_reads_schema_defining_preprocessing_and_domain_sources(
    monkeypatch,
) -> None:
    original = Path.read_bytes
    opened: list[Path] = []

    def spy(path: Path) -> bytes:
        opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", spy)
    digest = trainer._code_sha256(PROJECT)

    assert len(digest) == 64
    expected = {
        (PROJECT / "src/__init__.py").resolve(),
        (PROJECT / "src/config.py").resolve(),
        (PROJECT / "src/progress.py").resolve(),
        (PROJECT / "src/validation.py").resolve(),
    }
    for package in ("artifacts", "cli", "domain", "preprocessing", "training"):
        expected.update(path.resolve() for path in (PROJECT / "src" / package).glob("*.py"))
    assert set(opened) == expected


def test_progress_factory_is_used_for_five_folds_and_final_fit() -> None:
    protocol = load_xgboost_protocol(PROJECT / "config/xgboost_protocol_v1.yaml")
    frame = development_frame()
    frame["m4l"] = 125.0
    calls: list[dict[str, object]] = []

    class Progress:
        def set_postfix(self, *args, **kwargs) -> None:
            pass

        def update(self, amount: int) -> None:
            pass

        def close(self) -> None:
            pass

    def progress_factory(**options: object) -> Progress:
        calls.append(dict(options))
        return Progress()

    evidence = build_development_evidence(
        frame,
        protocol,
        model_factory=lambda **parameters: FakeClassifier(**parameters),
        show_progress=True,
        progress_factory=progress_factory,
    )
    assert evidence.qualification["eligible"] is True
    fit_final_model(
        frame,
        protocol,
        evidence,
        model_factory=lambda **parameters: FakeClassifier(**parameters),
        show_progress=True,
        progress_factory=progress_factory,
    )

    assert [call["desc"] for call in calls] == [
        "Candidate 1/1 fold 1/5",
        "Candidate 1/1 fold 2/5",
        "Candidate 1/1 fold 3/5",
        "Candidate 1/1 fold 4/5",
        "Candidate 1/1 fold 5/5",
        "Final model",
    ]
    assert [call["leave"] for call in calls] == [False] * 5 + [True]
