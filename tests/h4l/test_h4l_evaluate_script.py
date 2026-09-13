import json
from pathlib import Path
import subprocess
import sys
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "h4l_evaluate.py"
EXAMPLE = PROJECT_ROOT / "config" / "examples" / "h4l_evaluation_plan.json"


def invoke(plan):
    output = PROJECT_ROOT / "runs" / f"pytest-evaluate-plan-{uuid.uuid4().hex}"
    return subprocess.run([sys.executable, str(SCRIPT), "--plan", str(plan),
        "--prepared-run", "runs/missing-prepare", "--template-run", "runs/missing-template",
        "--freeze-run", "runs/missing-freeze", "--output-root", str(output), "--plan-only"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)


def test_evaluation_plan_only_prints_registered_25_stage_matrix():
    completed = invoke(EXAMPLE)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count("python.exe -m higgsml.cli") == 25
    assert "registration=exploratory_posthoc" in completed.stdout
    assert "input receipts deferred" in completed.stdout
    assert "normalization-minus1-omitted" in completed.stdout
    assert "correlation-plus1-modeled" in completed.stdout
    assert "--evaluation-plan" in completed.stdout


def test_evaluation_plan_rejects_protocol_or_t2_budget_changes(tmp_path):
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    value["t2"]["inner_toys"] += 1
    path = tmp_path / "bad-plan.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    completed = invoke(path)
    assert completed.returncode == 3
    assert "T2 plan differs" in completed.stderr

    value["t2"]["inner_toys"] -= 1
    value["protocol_sha256"] = "0" * 64
    path.write_text(json.dumps(value), encoding="utf-8")
    completed = invoke(path)
    assert completed.returncode == 3
    assert "protocol digest mismatch" in completed.stderr
