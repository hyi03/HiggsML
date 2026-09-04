from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_exact_console_entry_points() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"] == {
        "higgsml-preprocess": "src.cli.preprocess:main",
        "higgsml-train": "src.cli.train:main",
        "higgsml-test": "src.cli.test:main",
    }


def test_runtime_source_does_not_import_xgboost() -> None:
    violations: list[str] = []
    for path in (PROJECT_ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "xgboost" or name.startswith("xgboost.") for name in names):
                violations.append(str(path.relative_to(PROJECT_ROOT)))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            first_arg = node.args[0]
            if (
                function_name in {"__import__", "import_module"}
                and isinstance(first_arg, ast.Constant)
                and isinstance(first_arg.value, str)
                and (first_arg.value == "xgboost" or first_arg.value.startswith("xgboost."))
            ):
                violations.append(str(path.relative_to(PROJECT_ROOT)))

    assert violations == []


def test_environment_matches_package_runtime_pins_and_locks() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (PROJECT_ROOT / "environment.yml").read_text(encoding="utf-8")
    )
    conda_specs = {
        item.split("=", 1)[0].lower(): item.split("=", 1)[1]
        for item in environment["dependencies"]
        if isinstance(item, str) and "=" in item
    }
    pip_specs = {
        item.split("==", 1)[0].lower(): item.split("==", 1)[1]
        for group in environment["dependencies"]
        if isinstance(group, dict)
        for item in group.get("pip", [])
    }
    environment_pins = conda_specs | pip_specs
    package_pins = {
        spec.split("==", 1)[0].lower(): spec.split("==", 1)[1]
        for spec in metadata["project"]["dependencies"]
    }
    package_pins["pytorch"] = package_pins.pop("torch")

    assert package_pins.items() <= environment_pins.items()
    assert "conda-lock" in environment["dependencies"]
    for lock_name in ("osx.yml", "win.yml"):
        lock = yaml.safe_load((PROJECT_ROOT / lock_name).read_text(encoding="utf-8"))
        assert lock["metadata"]["sources"] == ["environment.yml"]
        assert any(package["name"] == "conda-lock" for package in lock["package"])
