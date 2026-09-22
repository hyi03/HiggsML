"""Read published aggregate artifacts; never open events or run inference."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
from statistics import median

PAPER_DIR = Path(__file__).resolve().parents[1]
ROOT = PAPER_DIR.parent
STUDY = ROOT / "runs/h4l-off-test01"
REPORT = STUDY / "evaluation/report"
SEEDS = list(range(42, 47))
GROUPS = "ABCD"
SUBSETS = ["".join(s) for n in range(5) for s in itertools.combinations(GROUPS, n)]
SOURCES = {}


def published(directory, name):
    """Verify bytes against the enclosing published manifest before reading."""
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = directory / name
    raw = path.read_bytes()
    expected = manifest["files"][name]
    sha = hashlib.sha256(raw).hexdigest()
    if len(raw) != expected["size_bytes"] or sha != expected["sha256"]:
        raise ValueError(f"Manifest mismatch: {path}")
    SOURCES[path.relative_to(ROOT).as_posix()] = {
        "artifact_id": manifest["artifact_id"], "sha256": sha,
        "size_bytes": len(raw), "stage": manifest["stage"],
        "protocol_sha256": manifest.get("protocol_sha256"),
        "git_commit": manifest.get("software", {}).get("git_commit"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    return raw.decode("utf-8")


def read_json(directory, name):
    return json.loads(published(directory, name))


def read_csv(name):
    return list(csv.DictReader(published(REPORT, name).splitlines()))


def close(actual, expected):
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"Aggregate mismatch: {actual!r} != {expected!r}")


def main():
    rows = read_csv("mass_off_feature_metrics.csv")
    assert len(rows) == 80
    widths, aucs = {}, {}
    for row in rows:
        seed, subset = int(row["seed"]), row["subset"]
        assert seed in SEEDS and subset in SUBSETS
        assert row["status"] == "valid" and row["value_source"] == "nominal_asimov"
        assert (seed, subset) not in widths
        widths[seed, subset] = float(row["width68"])
        aucs[seed, subset] = float(row["auc"]) if row["auc"] else None
        if subset:
            assert row["auc_role"] == "validation"
            assert row["auc_measure"] == "absolute_physical_weight"
            assert row["model_id"] == row["auc_model_id"]
    assert len({r["cohort_id"] for r in rows}) == 1
    assert len({r["family_id"] for r in rows}) == 1
    for seed in SEEDS:
        close(widths[seed, ""], widths[42, ""])
    inference = read_json(STUDY / "asimov", "inference.json")
    saved_summary = read_json(STUDY / "asimov", "summary.json")
    for row in rows:
        result = inference[row["candidate_key"]]
        interval = next(i for i in result["results"][0]["intervals"] if i["confidence"] == .68)
        assert result["layer"] == "T1" and result["results"][0]["mu"] == 1
        close(interval["width"], float(row["width68"]))
    freeze = read_json(STUDY / "freeze", "freeze.json")
    protocol = read_json(REPORT, "protocol.json")
    assert freeze["mass_edges"] == [105, 140]
    assert protocol["luminosity_pb"] == 10000
    attribution = read_csv("mass_off_feature_attribution.csv")
    interactions = read_csv("mass_off_feature_interactions.csv")
    pair_rows = read_csv("mass_off_pairwise_comparisons.csv")
    phi = {}
    residuals = []
    for seed in SEEDS:
        def value(subset):
            return -widths[seed, "".join(sorted(subset))]
        for group in GROUPS:
            phi[seed, group] = sum(
                math.factorial(len(s)) * math.factorial(3-len(s)) / math.factorial(4)
                * (value(s+group) - value(s)) for s in SUBSETS if group not in s
            )
        residuals.append(sum(phi[seed, g] for g in GROUPS) - (value(GROUPS)-value("")))
        close(residuals[-1], 0)
    for row in attribution:
        per_seed = [phi[s, row["group"]] for s in SEEDS]
        for actual, expected in zip(per_seed, json.loads(row["per_seed"])):
            close(actual, expected)
        close(median(per_seed), float(row["median"]))
    for row in interactions:
        conditioning, pair = row["conditioning_subset"], row["pair"]
        # CSV serializes the pair as a two-element JSON list.
        i, j = json.loads(pair) if pair.startswith("[") else pair
        vals = []
        for seed in SEEDS:
            def value(s):
                return -widths[seed, "".join(sorted(s))]
            vals.append(value(conditioning+i+j)-value(conditioning+i)-value(conditioning+j)+value(conditioning))
        for actual, expected in zip(vals, json.loads(row["per_seed"])):
            close(actual, expected)
        close(median(vals), float(row["median"]))
    for row in pair_rows:
        left, right = row["left"], row["right"]
        diffs = [widths[s, left]-widths[s, right] for s in SEEDS]
        ratios = [1-widths[s, left]/widths[s, right] for s in SEEDS]
        for key, vals in [("delta_width68_left_minus_right", diffs), ("relative_improvement_left_vs_right", ratios)]:
            saved = json.loads(row[key])
            close(median(vals), saved["median"])
            for actual, expected in zip(vals, saved["per_seed"]):
                close(actual, expected)
    assert len(attribution) == 4 and len(interactions) == 24 and len(pair_rows) == 105
    completeness = read_csv("evaluation_completeness.csv")
    diagnostics = read_csv("five_seed_descriptive_diagnostics.csv")
    bootstrap_intervals = read_csv("mc_bootstrap_uncertainty.csv")
    assert all(not r["interval68"] and not r["interval95"] for r in bootstrap_intervals)
    bootstrap = read_json(STUDY / "evaluation/mc-bootstrap-mu1", "evaluation.json")
    bootstrap_meta = {k: v for k, v in bootstrap.items() if not isinstance(v, (list, dict))}
    audit = read_json(ROOT / "runs/h4l-prepare/prepare", "audit.json")
    access = read_json(STUDY / "access-review", "validated-off-assessment-access.json")
    assert SOURCES["runs/h4l-prepare/prepare/audit.json"]["artifact_id"] == freeze["prepared_artifact_id"]
    assert {r["cohort_id"] for r in rows} == {freeze["template_artifact_id"]}
    assert all(s["protocol_sha256"] == freeze["protocol_sha256"] for s in SOURCES.values())
    assert access["independent"] is False
    # Only retain the published status and counts, never identity or event payload.
    snapshot = {
        "description": "Published aggregate results only; no refits, events, or new pseudo-experiments",
        "seeds": SEEDS, "subsets": SUBSETS,
        "records": [{**r, "seed": int(r["seed"]), "width68": float(r["width68"]),
                     "auc": float(r["auc"]) if r["auc"] else None} for r in rows],
        "attribution": [{"group": g, "per_seed": [phi[s, g] for s in SEEDS],
                         "median": median(phi[s, g] for s in SEEDS)} for g in GROUPS],
        "interactions": [{**r, "per_seed": json.loads(r["per_seed"]), "median": float(r["median"])} for r in interactions],
        "pairwise": [{**r, "delta_width68_left_minus_right": json.loads(r["delta_width68_left_minus_right"]),
                       "relative_improvement_left_vs_right": json.loads(r["relative_improvement_left_vs_right"])} for r in pair_rows],
        "diagnostics": diagnostics, "completeness": completeness,
        "bootstrap": bootstrap_meta, "prepared_audit": audit,
        "mass_edges": freeze["mass_edges"], "access_independent": access["independent"],
        "protocol": protocol, "auc_correlations": saved_summary["auc_width_relationship"],
        "example_model_spec": inference["M3:42:groups=BC:m4l=off"]["model_spec"],
    }
    # Large observation vectors in the saved summary are unnecessary for the paper.
    snapshot["auc_correlations"].pop("observations", None)
    provenance = {
        "snapshot_schema": "higgsml-paper-aggregate-v1", "checked_date": "2026-09-22",
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "sources": SOURCES, "max_shapley_efficiency_residual": max(map(abs, residuals)),
        "checks": {"nominal_candidates": 80, "shapley_groups": 4, "conditional_interactions": 24,
                   "nonempty_pairs": 105, "tolerance_rtol_atol": 1e-12},
        "scope": "Selected published aggregate files verified against their manifests; not a recursive lineage or independent physics audit",
        "old_document_difference": "paper/result-evidence.md names absent report-resume-6f5909a8b7f58d5e and different artifact IDs. This paper binds the present report directory. All 15 model-self cells are valid in that present report.",
    }
    out = PAPER_DIR / "evidence/data"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"verified_files": len(SOURCES), "nominal_rows": len(rows),
                      "max_efficiency_residual": max(map(abs, residuals)), "bootstrap": bootstrap_meta,
                      "status_counts": {status: sum(r["status"] == status for r in completeness)
                                        for status in sorted({r["status"] for r in completeness})}}, indent=2))


if __name__ == "__main__":
    main()
