from __future__ import annotations

import ast
from pathlib import Path

from src.config import ANGULAR19
from src.domain.angular5 import ANGULAR5_FEATURES
from src.domain.features import FEATURES, FORBIDDEN_FEATURES
from src.domain.split import event_split


def test_domain_exposes_exact_frozen_angular19_contract() -> None:
    assert ANGULAR19 == (*tuple(FEATURES), *ANGULAR5_FEATURES)
    assert len(ANGULAR19) == 19
    assert not set(ANGULAR19) & FORBIDDEN_FEATURES


def test_domain_split_matches_frozen_bucket_contract() -> None:
    assert [event_split(value, 345060) for value in (0, 10, 60, 80, 103)] == [
        "train",
        "validation",
        "test",
        "validation",
        "test",
    ]


def test_domain_modules_have_no_filesystem_cli_plotting_or_xgboost_imports() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "domain"
    forbidden = {"argparse", "pathlib", "matplotlib", "mplhep", "uproot", "xgboost"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imported.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        )
        assert not imported & forbidden, (path.name, imported & forbidden)
