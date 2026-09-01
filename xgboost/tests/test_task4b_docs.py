import re
from pathlib import Path


def test_task4b_completion_is_documented_consistently() -> None:
    project_root = Path(__file__).resolve().parents[1]
    primary_documents = (
        project_root / "README.md",
        project_root / "AGENTS.md",
        project_root / "docs/project/overview.md",
        project_root / "docs/roadmap/next-stage.md",
    )
    required_completion_facts = (
        "python -m scripts.train_full_mc",
        "--input-run runs/full-baseline-2026-08-10",
        "--config config/full_training.yaml",
        "--run-dir runs/full-training-2026-08-11",
        "runs/full-baseline-2026-08-10",
        "config/full_training.yaml",
        "runs/full-training-2026-08-11",
        "manifest schema 为 `1.0`",
        "全量 MC `351399`",
        "development OOF `281249`",
        "independent test `70150`",
        "`depth2_child20`",
        "最终树数 `124`",
        "OOF weighted AUC `0.7819012512935757`",
        "test weighted AUC `0.844677675856134`",
        "loose `0.4421731233596802`",
        "medium `0.6183240413665771`",
        "tight `0.6919658780097961`",
        "loose `0.5004580267548995 / 0.8806158272151767`",
        "medium `0.20065226444487125 / 0.5799549950508799`",
        "tight `0.1005088836655481 / 0.4257204708429173`",
        "loose `0.4253686842730043 / 0.8807478236049668`",
        "medium `0.11723106326431036 / 0.602126444983588`",
        "tight `0.0556776426566235 / 0.43029827315541624`",
        "background KS distance `0.1903422555517139`",
        "signal KS distance `0.023516517743828735`",
        "总 warning 为 `true`，唯一原因是 `background_ks_distance`",
        "mass-sculpting warning 为 `false`",
        "selected ZZ 总数 `471`（`391 development`、`80 test`）",
        "五张批准图均只使用 MC",
        "质量图只包含 ZZ",
        "383 passed",
        "Task 4B 未读取或评分真实数据",
        "不声称在真实数据中观察到 125 GeV Higgs 峰",
        "当前下一阶段是质量去相关训练研究；不得事后放宽 AUC/KS 门槛或打开真实数据。",
    )

    for document in primary_documents:
        text = document.read_text(encoding="utf-8")
        for fact in required_completion_facts:
            assert fact in text, f"{document.relative_to(project_root)} missing {fact!r}"

    docs_index = (project_root / "docs/README.md").read_text(encoding="utf-8")
    assert "superpowers/specs/2026-08-10-task-4b-full-mc-training-design.md" in docs_index
    assert "superpowers/plans/2026-08-10-task-4b-full-mc-training.md" in docs_index

    indexed_live_documents = (
        project_root / "docs/project/overview.md",
        project_root / "docs/physics/data-description.md",
        project_root / "docs/physics/selection-standard.md",
        project_root / "docs/roadmap/next-stage.md",
        project_root / "docs/briefings/progress-briefing.md",
        project_root / "docs/superpowers/specs/2026-08-10-task-4b-full-mc-training-design.md",
        project_root / "docs/superpowers/plans/2026-08-10-task-4b-full-mc-training.md",
    )
    stale_task4b_status = (
        r"Task 4B\s*(?:[：:]\s*)?(?:（[^）]*）\s*)?(?:的\s*[^。\n]{0,60})?(?:仍未实现|尚未实现|待实现|（未实现）)",
        r"(?:下一步|下一项推荐开发任务)[^。\n]{0,60}Task 4B",
        r"第一优先级：设计 Task 4B",
    )
    previously_observed_stale_status = (
        "Task 4B 的类别平衡、确定性抽样和训练权重政策尚未实现；",
        "Task 4B 的类别平衡、抽样和训练权重政策仍未实现。",
    )
    for stale_text in previously_observed_stale_status:
        assert any(re.search(pattern, stale_text) for pattern in stale_task4b_status), (
            f"no stale-status regex detects {stale_text!r}"
        )

    for document in indexed_live_documents:
        relative_path = document.relative_to(project_root / "docs").as_posix()
        assert relative_path in docs_index
        text = document.read_text(encoding="utf-8")
        for pattern in stale_task4b_status:
            assert re.search(pattern, text) is None, (
                f"{document.relative_to(project_root)} has stale Task 4B status: {pattern!r}"
            )

    briefing = (project_root / "docs/briefings/progress-briefing.md").read_text(
        encoding="utf-8"
    )
    for fact in (
        "Task 4B 全量 MC 训练审计（完成，2026-08-11）",
        "selected ZZ 总数 `471`（`391 development`、`80 test`）",
        "总 warning 为 `true`，唯一原因是 `background_ks_distance`",
        "Task 4B 未读取或评分真实数据",
        "下一阶段是扩充 data periods，并单独设计冻结模型的盲化数据应用",
    ):
        assert fact in briefing


def test_full14_is_retired_consistently_as_a_failed_historical_reference() -> None:
    project_root = Path(__file__).resolve().parents[1]
    primary_documents = (
        project_root / "README.md",
        project_root / "AGENTS.md",
        project_root / "docs/project/overview.md",
        project_root / "docs/roadmap/next-stage.md",
    )
    required_retirement_facts = (
        "Full14 XGBoost 已封存为失败的历史参考",
        "不是可部署模型，也不是未来真实数据候选",
        "停止 Full14 + OOF 质量依赖阈值研究",
        "不得读取 periodA",
        "AUC >= 0.80",
        "三个工作点 KS <= 0.10",
        "新配置和新 run path",
    )

    for document in primary_documents:
        text = document.read_text(encoding="utf-8")
        for fact in required_retirement_facts:
            assert fact in text, f"{document.relative_to(project_root)} missing {fact!r}"
