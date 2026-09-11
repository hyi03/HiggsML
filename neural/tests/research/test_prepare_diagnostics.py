import io
import json
import os

import awkward as ak
import numpy as np
import pandas as pd
import pytest

from src.cli.research import build_parser
from src.research.artifacts import read_run
from src.research.data import (
    PrepareEventProgress,
    PrepareProgressReporter,
    assign_roles,
    current_rss_bytes,
    finalize_prepare_metrics,
    iter_development_events,
    limit_selected_entries,
)
from src.research.errors import ResearchError
from src.research.protocol import DEFAULT_PATH, load_protocol
from src.research.representations import ENGINEERED19
from src.research.workflow import execute


@pytest.mark.skipif(os.name != "nt", reason="Windows ctypes signature isolation")
def test_windows_rss_reader_recovers_from_foreign_ctypes_signature():
    import ctypes
    from ctypes import wintypes

    class ForeignCounters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD)]

    api = ctypes.windll.psapi.GetProcessMemoryInfo
    api.argtypes = [wintypes.HANDLE, ctypes.POINTER(ForeignCounters), wintypes.DWORD]

    assert current_rss_bytes() > 0


def test_root_reader_records_conversion_counts_and_span_shape():
    mask = np.array([True, True, False, True])

    class Tree:
        def arrays(self, names, *, entry_start, entry_stop, library):
            assert names == ["payload"] and library == "ak"
            return ak.Array({"payload": [[index] for index in range(entry_start, entry_stop)]})

    identities = {"event": np.arange(4), "channel": np.ones(4, dtype=int)}
    metrics = {}
    result = list(iter_development_events(
        Tree(),
        {"eventNumber": "event", "channelNumber": "channel", "x": "payload"},
        identities,
        mask,
        metrics=metrics,
    ))

    assert [entry for entry, _ in result] == [0, 1, 3]
    assert metrics["entries_processed"] == 3
    assert metrics["payload_requests"] == 2
    assert metrics["span_entries_total"] == 3
    assert metrics["conversion_seconds"] >= 0


def test_root_reader_forwards_bounded_executor_without_changing_ranges():
    executor = object()
    calls = []

    class Tree:
        def arrays(self, names, *, entry_start, entry_stop, library,
                   decompression_executor, interpretation_executor):
            calls.append((entry_start, entry_stop))
            assert names == ["payload"] and library == "ak"
            assert decompression_executor is executor
            assert interpretation_executor is executor
            return ak.Array({
                "payload": [[index] for index in range(entry_start, entry_stop)]
            })

    identities = {"event": np.arange(4), "channel": np.ones(4, dtype=int)}
    result = list(iter_development_events(
        Tree(),
        {"eventNumber": "event", "channelNumber": "channel", "x": "payload"},
        identities,
        [True, True, False, True],
        root_executor=executor,
    ))

    assert calls == [(0, 2), (3, 4)]
    assert [entry for entry, _ in result] == [0, 1, 3]


def test_progress_reporter_emits_bounded_live_throughput_and_rss():
    ticks = iter([100.0, 111.0])
    stream = io.StringIO()
    metrics = {
        "entries_processed": 220,
        "selected_entries": 17,
        "payload_requests": 44,
        "payload_seconds": 4.0,
        "conversion_seconds": 2.0,
        "selection_seconds": 3.0,
        "feature_seconds": 1.0,
    }
    reporter = PrepareProgressReporter(
        metrics,
        interval_seconds=10.0,
        clock=lambda: next(ticks),
        rss_reader=lambda: 64 * 1024 * 1024,
        stream=stream,
    )

    reporter.update()

    line = stream.getvalue()
    assert "entries=220" in line
    assert "selected=17" in line
    assert "spans=44" in line
    assert "rate=20.0 entries/s" in line
    assert "rss=64.0 MiB" in line
    assert metrics["peak_rss_bytes"] == 64 * 1024 * 1024


def test_event_progress_shows_percentage_counts_and_selected_total():
    stream = io.StringIO()
    metrics = {"selected_entries": 0}
    progress = PrepareEventProgress(metrics, 718_995, stream=stream)

    metrics["selected_entries"] = 84_210
    progress.update(251_904)
    progress.close()

    output = stream.getvalue()
    assert "ROOT prepare: 35%" in output
    assert "251,904/718,995 events" in output
    assert "selected: 84,210" in output


def test_finalize_prepare_metrics_identifies_fragmented_root_reads():
    metrics = {
        "source_files_total": 2,
        "source_files_processed": 2,
        "source_entries_total": 1000,
        "eligible_entries_total": 600,
        "entries_processed": 600,
        "selected_entries": 25,
        "payload_requests": 200,
        "span_entries_total": 600,
        "identity_seconds": 1.0,
        "payload_seconds": 10.0,
        "conversion_seconds": 2.0,
        "selection_seconds": 3.0,
        "feature_seconds": 1.0,
        "dataframe_seconds": 0.5,
        "role_assignment_seconds": 0.5,
        "g0_seconds": 0.2,
        "p0_seconds": 0.1,
        "write_and_digest_seconds": 0.7,
        "artifact_registration_seconds": 0.1,
        "peak_rss_bytes": 1234,
        "wall_seconds": 20.0,
    }

    finalize_prepare_metrics(metrics)

    assert metrics["average_span_length"] == pytest.approx(3.0)
    assert metrics["throughput_entries_per_second"] == pytest.approx(30.0)
    assert metrics["diagnosis"]["dominant_phase"] == "payload"
    assert metrics["diagnosis"]["classification"] == "fragmented_root_io"
    assert metrics["diagnosis"]["accounted_fraction"] == pytest.approx(19.1 / 20.0)


def test_diagnostic_entry_limit_and_prepare_metrics_are_cli_visible():
    mask = limit_selected_entries([True, False, True, True], 2)
    assert mask.tolist() == [True, False, True, False]
    args = build_parser().parse_args([
        "prepare",
        "--dataset", "atlas2020_4lep",
        "--protocol", "protocol.json",
        "--run-dir", "runs/diagnostic",
        "--diagnostic-entries-per-file", "1000",
    ])
    assert args.diagnostic_entries_per_file == 1000
    assert args.show_prepare_metrics is False
    assert args.show_prepare_progress is False

    verbose = build_parser().parse_args([
        "prepare",
        "--dataset", "atlas2020_4lep",
        "--protocol", "protocol.json",
        "--run-dir", "runs/diagnostic",
        "--show-prepare-metrics",
    ])
    assert verbose.show_prepare_metrics is True

    progress = build_parser().parse_args([
        "prepare",
        "--dataset", "atlas2020_4lep",
        "--protocol", "protocol.json",
        "--run-dir", "runs/diagnostic",
        "--show-prepare-progress",
    ])
    assert progress.show_prepare_progress is True


def test_fixed_workload_diagnostic_publishes_terminal_metrics(
    tmp_path, monkeypatch, capsys,
):
    protocol = load_protocol()
    rows = []
    for index in range(100):
        row = dict.fromkeys(ENGINEERED19, 1.0)
        row.update(
            event_id=f"event:{index}", source_row_id=f"event:{index}",
            event_group_id=f"group:{index}", split="development",
            dataset="atlas2020_4lep", label=index % 2,
            physical_weight=1.0, m4l=125.0, y4l=0.0,
        )
        rows.append(row)
    frame = assign_roles(pd.DataFrame(rows), protocol)
    frame.attrs.update(source_kind="synthetic", source_evidence={})

    show_values = []

    def fake_export(*args, metrics, **kwargs):
        show_values.append(kwargs["show_prepare_metrics"])
        metrics.update(
            source_files_total=2, source_files_processed=2,
            source_entries_total=200, eligible_entries_total=100,
            entries_processed=100, selected_entries=100,
            payload_requests=4, span_entries_total=100,
            identity_seconds=0.01, payload_seconds=0.02,
            conversion_seconds=0.01, selection_seconds=0.01,
            feature_seconds=0.01, dataframe_seconds=0.01,
            role_assignment_seconds=0.01, peak_rss_bytes=1024,
        )
        return frame

    monkeypatch.setattr("src.research.workflow.export_research_data", fake_export)
    manifest = tmp_path / "input.json"
    manifest.write_text(json.dumps({"dataset": "atlas2020_4lep", "mc_only": True}))
    run_dir = tmp_path / "diagnostic"
    args = build_parser().parse_args([
        "prepare", "--dataset", "atlas2020_4lep",
        "--protocol", str(DEFAULT_PATH), "--run-dir", str(run_dir),
        "--input-manifest", str(manifest), "--profile", str(tmp_path / "profile"),
        "--diagnostic-entries-per-file", "50",
    ])

    result = execute(args, allowed_root=tmp_path)

    assert result["status"] == "diagnostic_complete"
    assert show_values == [False]
    assert "[h4l prepare]" not in capsys.readouterr().err
    assert result["publication_seconds"] >= 0
    assert result["prepare_diagnostics"]["diagnosis"]["dominant_phase"]

    verbose_dir = tmp_path / "diagnostic-verbose"
    verbose_args = build_parser().parse_args([
        "prepare", "--dataset", "atlas2020_4lep",
        "--protocol", str(DEFAULT_PATH), "--run-dir", str(verbose_dir),
        "--input-manifest", str(manifest), "--profile", str(tmp_path / "profile"),
        "--diagnostic-entries-per-file", "50",
        "--show-prepare-metrics",
    ])
    verbose_result = execute(verbose_args, allowed_root=tmp_path)

    assert verbose_result["status"] == "diagnostic_complete"
    assert show_values == [False, True]
    assert "[h4l prepare] diagnosis=" in capsys.readouterr().err

    terminal = read_run(
        run_dir, dataset="atlas2020_4lep", protocol=protocol.to_dict(),
        allow_terminal=True,
    )
    metrics = terminal.manifest["root_prepare_metrics"]
    for name in (
        "dataframe_seconds", "role_assignment_seconds", "g0_seconds",
        "p0_seconds", "write_and_digest_seconds",
        "artifact_registration_seconds", "peak_rss_bytes", "diagnosis",
    ):
        assert name in metrics
    with pytest.raises(ResearchError, match="not usable"):
        read_run(run_dir, dataset="atlas2020_4lep", protocol=protocol.to_dict())
