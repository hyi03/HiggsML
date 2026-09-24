"""Read published aggregate artifacts; never open events or run inference."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
from statistics import median

from higgsml.artifacts import digest_json
from higgsml.qualification import contract_qualification

PAPER_DIR = Path(__file__).resolve().parents[1]
ROOT = PAPER_DIR.parent
SEEDS = list(range(42, 47))
GROUPS = "ABCD"
SUBSETS = ["".join(s) for n in range(5) for s in itertools.combinations(GROUPS, n)]
SOURCES = {}
RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--report', type=Path, help='Explicit published report directory (Stage B or final).')
    source.add_argument('--evidence-manifest', type=Path, help='Report identity and relocation map JSON.')
    source.add_argument('--run-name', help='Short name for runs/h4l-off-<name>/evaluation/report.')
    parser.add_argument('--path-map', action='append', default=[], metavar='OLD=NEW')
    parser.add_argument('--output', type=Path, required=True, help='Fresh snapshot directory; never overwrite.')
    args = parser.parse_args()
    if args.run_name and RUN_NAME.fullmatch(args.run_name) is None:
        parser.error(
            "run name must contain 1-64 letters, digits, underscores, or hyphens "
            "and must start with a letter or digit"
        )
    return args


class EvidenceReader:
    """Read only selected aggregate files and manifest links, never event data."""

    def __init__(self, path_maps=()):
        self.path_maps = sorted([(Path(a).resolve(), Path(b).resolve()) for a, b in path_maps],
                                key=lambda p: len(p[0].parts), reverse=True)
        self.manifests = {}

    def relocate(self, path):
        path = Path(path).resolve()
        for old, new in self.path_maps:
            if path.is_relative_to(old):
                return new / path.relative_to(old)
        return path

    def manifest(self, directory):
        directory = Path(directory).resolve()
        if directory not in self.manifests:
            path = directory / 'manifest.json'
            if path.is_symlink():
                raise ValueError(f'Unsafe manifest: {path}')
            value = json.loads(path.read_text(encoding='utf-8'))
            identity = dict(value)
            artifact_id = identity.pop('artifact_id', None)
            if value.get('schema_version') != 'research-run-v1' or artifact_id != digest_json(identity):
                raise ValueError(f'Manifest identity mismatch: {directory}')
            self.manifests[directory] = value
        return self.manifests[directory]

    def upstream(self, directory, stage, *, artifact_id=None, optional=False):
        matches = [r for r in self.manifest(directory)['upstreams']
                   if r['stage'] == stage and (artifact_id is None or r['artifact_id'] == artifact_id)]
        if not matches and optional:
            return None
        if len(matches) != 1:
            raise ValueError(f'Expected one bound {stage} upstream of {directory}, found {len(matches)}')
        ref = matches[0]
        path = self.relocate(ref['path'])
        actual = self.manifest(path)
        if actual['artifact_id'] != ref['artifact_id'] or actual['stage'] != stage:
            raise ValueError(f'Upstream identity mismatch: {path}')
        return path

    def access(self, report):
        # Access is bound through the evaluated blocks, not guessed from a sibling
        # directory. Stage B has no such reference and remains pending.
        found = set()
        direct = self.upstream(report, 'attribution-v3-access-review', optional=True)
        if direct is not None:
            found.add(direct)
        for ref in self.manifest(report)['upstreams']:
            if ref['stage'] != 'marginal-block-evaluation':
                continue
            block = self.upstream(report, ref['stage'], artifact_id=ref['artifact_id'])
            access = self.upstream(block, 'attribution-v3-access-review', optional=True)
            if access is not None:
                found.add(access)
        if len(found) > 1:
            raise ValueError('Conflicting bound access receipts')
        return next(iter(found), None)


def published(directory, name):
    """Verify bytes against the enclosing published manifest before reading."""
    manifest_path = directory / "manifest.json"
    manifest = READER.manifest(directory)
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError(f"Unsafe aggregate path: {path}")
    raw = path.read_bytes()
    expected = manifest["files"][name]
    sha = hashlib.sha256(raw).hexdigest()
    if len(raw) != expected["size_bytes"] or sha != expected["sha256"]:
        raise ValueError(f"Manifest mismatch: {path}")
    SOURCES[str(path.resolve())] = {
        "artifact_id": manifest["artifact_id"], "sha256": sha,
        "size_bytes": len(raw), "stage": manifest["stage"],
        "protocol_sha256": manifest.get("protocol_sha256"),
        "git_commit": manifest.get("software", {}).get("git_commit"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    return raw.decode("utf-8")


def read_json(directory, name):
    return json.loads(published(directory, name))


def read_csv(report, name):
    return list(csv.DictReader(published(report, name).splitlines()))


def close(actual, expected):
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"Aggregate mismatch: {actual!r} != {expected!r}")


def collect(report, *, path_maps=(), expected_report_id=None, access_review=None):
    global READER
    SOURCES.clear()
    READER = EvidenceReader(path_maps)
    report = Path(report).resolve()
    report_manifest = READER.manifest(report)
    if report_manifest['stage'] != 'attribution-v3-report' or report_manifest['status'] != 'complete':
        raise ValueError('Expected a published v3 report')
    if expected_report_id and report_manifest['artifact_id'] != expected_report_id:
        raise ValueError('Selected report identity mismatch')
    asimov_path = READER.upstream(report, 'attribution-v3-asimov')
    freeze_path = READER.upstream(report, 'attribution-v3-freeze')
    freeze = read_json(freeze_path, 'freeze.json')
    register_path = READER.upstream(freeze_path, 'attribution-v3-register', artifact_id=freeze['registration_artifact_id'])
    prepared_path = READER.upstream(register_path, 'prepare', artifact_id=freeze['prepared_artifact_id'])
    nominal_path = READER.upstream(report, 'attribution-v3-nominal', artifact_id=freeze['template_artifact_id'])
    for directory in (report, asimov_path):
        if READER.upstream(directory, 'attribution-v3-freeze') != freeze_path:
            raise ValueError('Asimov/report freeze identity mismatch')
        if READER.upstream(directory, 'attribution-v3-register') != register_path:
            raise ValueError('Asimov/report registration identity mismatch')
        if READER.upstream(directory, 'attribution-v3-nominal') != nominal_path:
            raise ValueError('Asimov/report template identity mismatch')
    report_value = read_json(report, 'report.json')
    rows = read_csv(report, "mass_off_feature_metrics.csv")
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
    inference = read_json(asimov_path, "inference.json")
    saved_summary = read_json(asimov_path, "summary.json")
    for row in rows:
        result = inference[row["candidate_key"]]
        interval = next(i for i in result["results"][0]["intervals"] if i["confidence"] == .68)
        assert result["layer"] == "T1" and result["results"][0]["mu"] == 1
        close(interval["width"], float(row["width68"]))
    protocol = read_json(report, "protocol.json")
    if digest_json(protocol) != report_manifest['protocol_sha256'] or digest_json(protocol) != freeze['protocol_sha256']:
        raise ValueError('Protocol content/digest mismatch')
    attribution = read_csv(report, "mass_off_feature_attribution.csv")
    interactions = read_csv(report, "mass_off_feature_interactions.csv")
    pair_rows = read_csv(report, "mass_off_pairwise_comparisons.csv")
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
    completeness = read_csv(report, "evaluation_completeness.csv")
    diagnostics = read_csv(report, "five_seed_descriptive_diagnostics.csv")
    bootstrap_intervals = (read_csv(report, "mc_bootstrap_uncertainty.csv")
                           if 'mc_bootstrap_uncertainty.csv' in report_manifest['files'] else [])
    bootstrap_path = READER.upstream(report, 'attribution-v3-mc-bootstrap', optional=True)
    bootstrap_states = {r['status'] for r in completeness if r.get('stage') == 'mc-bootstrap'}
    if len(bootstrap_states) != 1:
        raise ValueError('Missing or conflicting bootstrap status')
    bootstrap_state = bootstrap_states.pop()
    bootstrap = (read_json(bootstrap_path, 'evaluation.json') if bootstrap_path else {'status': bootstrap_state})
    bootstrap_meta = {k: v for k, v in bootstrap.items() if not isinstance(v, (list, dict))}
    if bootstrap_path is None and bootstrap_state not in ('not_run', 'invalid_or_consumed_output'):
        raise ValueError('Report claims bootstrap output without a bound upstream')
    if bootstrap_path is None and any(r.get('interval68') or r.get('interval95') for r in bootstrap_intervals):
        raise ValueError('Unbound bootstrap intervals')
    audit = read_json(prepared_path, "audit.json")
    access_path = READER.access(report)
    if access_review:
        explicit = READER.relocate(access_review['path'])
        if READER.manifest(explicit)['artifact_id'] != access_review['artifact_id']:
            raise ValueError('Explicit access identity mismatch')
        if access_path is not None and explicit != access_path:
            raise ValueError('Conflicting explicit and upstream access receipts')
        access_path = explicit
    access = read_json(access_path, 'validated-off-assessment-access.json') if access_path else None
    if access:
        if READER.upstream(access_path, 'attribution-v3-freeze') != freeze_path:
            raise ValueError('Access freeze identity mismatch')
        if 'specification_id' in freeze and access.get('specification_id') != freeze['specification_id']:
            raise ValueError('Access specification identity mismatch')
    assert {r["cohort_id"] for r in rows} == {freeze["template_artifact_id"]}
    assert all(READER.manifest(p)['protocol_sha256'] == freeze['protocol_sha256']
               for p in (report, asimov_path, freeze_path, register_path, nominal_path))
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
        "mass_edges": freeze["mass_edges"], "access_independent": access["independent"] if access else None,
        "bootstrap_intervals": bootstrap_intervals,
        "publication_status": report_manifest['status'],
        "aggregate_status": report_value['aggregate_status'],
        "reported_qualification": report_value.get('qualification', {}),
        "reported_primary_claim_eligible": report_value.get('primary_claim_eligible', False),
        "qualification": contract_qualification(True),
        "report_artifact_id": report_manifest['artifact_id'],
        "protocol": protocol, "auc_correlations": saved_summary["auc_width_relationship"],
        "example_model_spec": inference["M3:42:groups=BC:m4l=off"]["model_spec"],
    }
    # Large observation vectors in the saved summary are unnecessary for the paper.
    snapshot["auc_correlations"].pop("observations", None)
    provenance = {
        "snapshot_schema": "higgsml-paper-aggregate-v2",
        "checked_date": datetime.now(timezone.utc).isoformat(),
        "report_artifact_id": report_manifest['artifact_id'],
        "execution_revisions": {k: READER.manifest(v).get('software', {}).get('git_commit')
                                for k,v in {'report':report, 'asimov':asimov_path, 'freeze':freeze_path, 'prepared':prepared_path}.items()},
        "path_maps": [{'original':str(a), 'archived':str(b)} for a,b in READER.path_maps],
        "bindings": {k: READER.manifest(v)['artifact_id'] for k,v in
                     {'report':report, 'asimov':asimov_path, 'freeze':freeze_path, 'prepared':prepared_path, 'registration':register_path, 'template':nominal_path}.items()},
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sources": dict(SOURCES), "max_shapley_efficiency_residual": max(map(abs, residuals)),
        "checks": {"nominal_candidates": 80, "shapley_groups": 4, "conditional_interactions": 24,
                   "nonempty_pairs": 105, "tolerance_rtol_atol": 1e-12},
        "scope": "Selected published aggregate files verified against their manifests; not a recursive lineage or independent physics audit",
    }
    provenance['manifests'] = {str(path): {'artifact_id': m['artifact_id'],
        'sha256': hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()}
        for path,m in READER.manifests.items()}
    return snapshot, provenance


def main():
    args = parse_args()
    maps = [tuple(item.split('=', 1)) for item in args.path_map]
    if any(len(item) != 2 for item in maps):
        raise ValueError('--path-map requires OLD=NEW')
    selected = {}
    if args.evidence_manifest:
        selected = json.loads(args.evidence_manifest.read_text(encoding='utf-8'))
        maps += [(r['original'], r['archived']) for r in selected.get('path_maps', [])]
    report = selected.get('report') or args.report or ROOT/'runs'/f'h4l-off-{args.run_name}'/'evaluation/report'
    if args.output.exists():
        raise ValueError('Snapshot output already exists; select a fresh directory')
    snapshot, provenance = collect(report, path_maps=maps, expected_report_id=selected.get('report_artifact_id'),
                                   access_review=selected.get('access_review'))
    raw = (json.dumps(snapshot, indent=2, allow_nan=False)+'\n').encode('utf-8')
    provenance['snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'results.json').write_bytes(raw)
    (args.output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output':str(args.output), 'verified_files':len(provenance['sources']),
                      'report_artifact_id':snapshot['report_artifact_id'],
                      'aggregate_status':snapshot['aggregate_status'], 'bootstrap':snapshot['bootstrap']}, indent=2))


if __name__ == "__main__":
    main()
