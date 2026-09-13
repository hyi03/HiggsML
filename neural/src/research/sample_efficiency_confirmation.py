"""Claim-before-decode confirmation boundary for sample-efficiency studies."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat

import numpy as np

from .artifacts import ResearchRun, digest_json, read_json, read_run
from .data import population_digest
from .errors import ResearchError, ResearchStateError
from .protocol import ResearchProtocol, canonical
from .sample_efficiency_protocol import CompactCandidateFreeze, SampleEfficiencyProtocol

INPUT_SCHEMA = "h4l-noninferiority-evaluation-input-v1"
EXCLUSION_SCHEMA = "h4l-excluded-identity-set-v1"
CONFIRMATION_SCHEMA = "h4l-noninferiority-confirmation-v1"
CONFIRMATION_STAGE = "sample-efficiency-confirmation"
CLAIM_NAMESPACE = "h4l-sample-efficiency-confirmation-v1"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 4 * 1024 * 1024
IDENTITY_KEYS = {"event_group_id", "label", "role", "split", "dataset"}
HEADER_KEYS = {
    "schema_version", "dataset", "source_kind", "base_research_protocol_sha256",
    "sample_efficiency_protocol_sha256", "compact_freeze_artifact_id",
    "compact_freeze_sha256", "bootstrap_unit", "bootstrap_replicates",
    "bootstrap_seed", "ci_algorithm", "confidence_level", "delta_w68",
    "evaluation_package_id",
}
REPLICATE_KEYS = {
    "index", "multiplicity_digest", "compact_w68", "reference_w68",
    "difference", "compact_pointer", "reference_pointer",
}
RECEIPT_KEYS = {
    "role", "representation_id", "population_id", "artifact_id", "stage",
    "sha256", "pointer",
}
EVALUATION_RECEIPT_SPECS = (
    ("compact_model", "noninferiority-evaluation-model", "compact", "/model"),
    ("compact_calibration", "noninferiority-evaluation-calibration", "compact", "/calibration"),
    ("compact_template", "noninferiority-evaluation-template", "compact", "/template"),
    ("compact_inference", "noninferiority-evaluation-inference", "compact", "/result"),
    ("reference_model", "noninferiority-evaluation-model", "reference", "/model"),
    ("reference_calibration", "noninferiority-evaluation-calibration", "reference", "/calibration"),
    ("reference_template", "noninferiority-evaluation-template", "reference", "/template"),
    ("reference_inference", "noninferiority-evaluation-inference", "reference", "/result"),
    ("common_grid", "noninferiority-evaluation-common-grid", "shared", "/grid"),
    ("multiplicity_plan", "noninferiority-evaluation-multiplicity-plan", "shared", "/plan"),
)
PRECLAIM_SCHEMA = "h4l-confirmation-preclaim-v1"
PRECLAIM_KEYS = {
    "schema_version", "attempt_id", "claim_key", "population_id", "input_sha256",
    "size_bytes", "exclusion_receipts",
}
EXCLUSION_RECEIPT_KEYS = {
    "identity_set_id", "population_id", "sha256", "size_bytes", "path",
}
PAYLOAD_KEYS = HEADER_KEYS | {
    "population_id", "compact_representation", "reference_representation",
    "canonical_event_group_order", "multiplicity_plan_id", "replicates",
    "evaluation_artifact_receipts", "validation_scope", "payload_id",
}


def _fail(message, *, status="training_subset_binding_mismatch"):
    raise ResearchError(message, status=status)


def _strict_json(data):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        return json.loads(
            data, object_pairs_hook=object_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise ResearchError("invalid canonical confirmation JSON") from exc


def _is_sha(value):
    return (
        type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _regular_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        _fail("confirmation input must be a regular non-link file")
    return path


def expected_header(base, overlay, freeze, freeze_artifact_id):
    return {
        "schema_version": INPUT_SCHEMA,
        "dataset": base["dataset"],
        "base_research_protocol_sha256": base.digest,
        "sample_efficiency_protocol_sha256": overlay.digest,
        "compact_freeze_artifact_id": freeze_artifact_id,
        "compact_freeze_sha256": freeze.digest,
        "bootstrap_unit": overlay["noninferiority"]["bootstrap_unit"],
        "bootstrap_replicates": overlay["noninferiority"]["bootstrap_replicates"],
        "bootstrap_seed": overlay["noninferiority"]["bootstrap_seed"],
        "ci_algorithm": overlay["noninferiority"]["ci_algorithm"],
        "confidence_level": overlay["noninferiority"]["confidence_level"],
        "delta_w68": overlay["noninferiority"]["delta_w68"],
    }


@dataclass(frozen=True)
class PreclaimScan:
    header: dict
    event_group_ids: tuple
    population_id: str
    file_sha256: str
    size_bytes: int
    payload_offset: int
    file_stat: tuple


def scan_confirmation_handle(stream, *, base, overlay, freeze, freeze_artifact_id):
    """Read only the header and identity region; payload remains uninterpreted."""
    if not isinstance(base, ResearchProtocol) or not isinstance(overlay, SampleEfficiencyProtocol):
        _fail("validated protocols are required")
    if not isinstance(freeze, CompactCandidateFreeze):
        _fail("validated compact freeze is required")
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE_BYTES:
        _fail("invalid confirmation input size or type")
    stream.seek(0)
    digest = hashlib.sha256()
    prefix_lines = []
    payload_offset = None
    delimiter_count = 0
    payload_line_count = 0
    while True:
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_LINE_BYTES or b"\r" in line or not line.endswith(b"\n"):
            _fail("confirmation input requires bounded LF-terminated lines")
        digest.update(line)
        if line == b"--PAYLOAD--\n":
            delimiter_count += 1
            if payload_offset is None:
                payload_offset = stream.tell()
        elif payload_offset is None:
            prefix_lines.append(line[:-1])
        else:
            payload_line_count += 1
    if (stream.tell() != info.st_size or payload_offset is None or len(prefix_lines) < 3
            or delimiter_count != 1 or payload_line_count != 1):
        _fail("invalid confirmation input grammar")
    if prefix_lines[0].startswith(b"\xef\xbb\xbf"):
        _fail("confirmation input BOM is forbidden")
    header = _strict_json(prefix_lines[0])
    if type(header) is not dict or set(header) != HEADER_KEYS or canonical(header) != prefix_lines[0]:
        _fail("invalid canonical confirmation header")
    expected = expected_header(base, overlay, freeze, freeze_artifact_id)
    if any(header.get(key) != value for key, value in expected.items()):
        _fail("confirmation header differs from frozen inputs")
    if header["source_kind"] not in {"synthetic", "controlled_mc"} or not _is_sha(header["evaluation_package_id"]):
        _fail("invalid confirmation source or package identity")
    groups, labels, population = set(), set(), set()
    for raw in prefix_lines[1:]:
        if not raw.endswith(b"\t") or raw.count(b"\t") != 1:
            _fail("invalid confirmation identity line")
        identity = _strict_json(raw[:-1])
        if (
            type(identity) is not dict or set(identity) != IDENTITY_KEYS
            or canonical(identity) != raw[:-1]
            or type(identity["event_group_id"]) is not str or not identity["event_group_id"]
            or identity["event_group_id"] in groups
            or identity["label"] not in {0, 1}
            or identity["role"] != "assessment"
            or identity["split"] != "development"
            or identity["dataset"] != base["dataset"]
        ):
            _fail("invalid, duplicate, or conflicting confirmation identity")
        groups.add(identity["event_group_id"])
        labels.add(identity["label"])
        population.add((
            identity["event_group_id"], identity["label"],
            identity["split"], identity["dataset"],
        ))
    if labels != {0, 1}:
        _fail("confirmation identities require both labels")
    return PreclaimScan(
        header, tuple(sorted(groups)), population_digest(population, base["dataset"]),
        digest.hexdigest(), info.st_size, payload_offset,
        (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns),
    )


def load_exclusion_identity_sets(paths, *, dataset):
    groups, receipts = set(), []
    seen_sets = set()
    for path_value in paths:
        path = _regular_file(path_value)
        value = read_json(path)
        if (
            type(value) is not dict
            or set(value) != {
                "schema_version", "dataset", "population_id",
                "event_group_ids", "identity_set_id",
            }
            or value["schema_version"] != EXCLUSION_SCHEMA
            or value["dataset"] != dataset
            or type(value["population_id"]) is not str or not value["population_id"]
            or type(value["event_group_ids"]) is not list
            or value["event_group_ids"] != sorted(set(value["event_group_ids"]))
            or any(type(group) is not str or not group for group in value["event_group_ids"])
            or value.get("identity_set_id") in seen_sets
        ):
            _fail("invalid exclusion identity set")
        content = {key: item for key, item in value.items() if key != "identity_set_id"}
        if value["identity_set_id"] != digest_json(content):
            _fail("exclusion identity set digest mismatch")
        seen_sets.add(value["identity_set_id"])
        groups.update(value["event_group_ids"])
        receipts.append({
            "identity_set_id": value["identity_set_id"],
            "population_id": value["population_id"],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
            "path": str(path.resolve()),
        })
    return groups, receipts


def _validate_exclusion_coverage(scan, receipts, excluded, *, overlay, freeze):
    required = set(freeze["excluded_population_ids"]) | {overlay["population_id"]}
    supplied = [item["population_id"] for item in receipts]
    if set(supplied) != required or len(supplied) != len(required):
        _fail(
            "exclusion identity sets do not exactly cover frozen and M4/M5 populations",
            status="confirmation_population_not_independent",
        )
    if excluded & set(scan.event_group_ids):
        _fail(
            "confirmation population overlaps excluded lineage",
            status="confirmation_population_not_independent",
        )
    frozen_populations = set(
        freeze["discovery_population_ids"]
        + freeze["browsed_population_ids"]
        + freeze["excluded_population_ids"]
    )
    if scan.population_id in frozen_populations or scan.population_id == overlay["population_id"]:
        _fail(
            "confirmation population is not independent",
            status="confirmation_population_not_independent",
        )


def _expected_receipt_representation(kind, *, freeze):
    if kind == "compact":
        return freeze["candidate"]["representation_id"]
    if kind == "reference":
        return "engineered19"
    return "shared"


def _validate_payload(payload, scan, *, overlay, freeze):
    if type(payload) is not dict or set(payload) != PAYLOAD_KEYS:
        _fail("invalid confirmation payload schema")
    content = {key: value for key, value in payload.items() if key != "payload_id"}
    if payload["payload_id"] != digest_json(content):
        _fail("confirmation payload digest mismatch")
    if any(payload.get(key) != value for key, value in scan.header.items()):
        _fail("confirmation payload differs from preclaim header")
    if (
        payload["population_id"] != scan.population_id
        or payload["canonical_event_group_order"] != list(scan.event_group_ids)
        or payload["compact_representation"] != freeze["candidate"]["representation_id"]
        or payload["reference_representation"] != "engineered19"
    ):
        _fail("confirmation payload population or representation mismatch")
    expected_scope = (
        "synthetic_software_validation"
        if scan.header["source_kind"] == "synthetic"
        else "controlled_mc_external_pending"
    )
    if payload["validation_scope"] != expected_scope:
        _fail("confirmation validation scope mismatch")
    replicates = payload["replicates"]
    count = overlay["noninferiority"]["bootstrap_replicates"]
    if type(replicates) is not list or len(replicates) != count:
        _fail("confirmation replicate count mismatch")
    differences, multiplicities = [], []
    for index, record in enumerate(replicates):
        if type(record) is not dict or set(record) != REPLICATE_KEYS or record["index"] != index:
            _fail("invalid confirmation replicate")
        if not _is_sha(record["multiplicity_digest"]):
            _fail("invalid confirmation multiplicity digest")
        if any(
            type(record[key]) not in (int, float) or not np.isfinite(record[key])
            for key in ("compact_w68", "reference_w68", "difference")
        ):
            _fail("nonfinite confirmation replicate")
        if record["difference"] != record["compact_w68"] - record["reference_w68"]:
            _fail("confirmation difference is not replayable")
        if any(type(record[key]) is not str or not record[key] for key in ("compact_pointer", "reference_pointer")):
            _fail("invalid confirmation metric pointer")
        differences.append(float(record["difference"]))
        multiplicities.append(record["multiplicity_digest"])
    plan = {
        "seed": overlay["noninferiority"]["bootstrap_seed"],
        "unit": "event_group_id",
        "group_order": list(scan.event_group_ids),
        "replicates": multiplicities,
    }
    if payload["multiplicity_plan_id"] != digest_json(plan):
        _fail("confirmation multiplicity plan mismatch")
    receipts = payload["evaluation_artifact_receipts"]
    if type(receipts) is not list or len(receipts) != len(EVALUATION_RECEIPT_SPECS):
        _fail("invalid evaluation package receipts")
    artifact_ids = set()
    for item, (role, stage, kind, pointer) in zip(receipts, EVALUATION_RECEIPT_SPECS):
        if (
            type(item) is not dict or set(item) != RECEIPT_KEYS
            or item["role"] != role or item["stage"] != stage
            or item["representation_id"]
            != _expected_receipt_representation(kind, freeze=freeze)
            or item["population_id"] != scan.population_id
            or item["pointer"] != pointer
            or not _is_sha(item["artifact_id"]) or not _is_sha(item["sha256"])
            or item["artifact_id"] in artifact_ids
        ):
            _fail("invalid evaluation package receipts")
        artifact_ids.add(item["artifact_id"])
    if scan.header["evaluation_package_id"] != digest_json(receipts):
        _fail("invalid evaluation package receipts")
    return np.asarray(differences, dtype=float)


def _validate_upstreams(upstreams, freeze_artifact_id, *, base, freeze):
    if (
        len(upstreams) != 3
        or [item.manifest.get("stage") for item in upstreams]
        != ["compact-freeze", "sample-efficiency-batch", "sample-efficiency-report"]
        or upstreams[0].manifest.get("artifact_id") != freeze_artifact_id
    ):
        _fail("confirmation requires freeze, verified M4 batch, and M5 report upstreams")
    verified = []
    for supplied, stage in zip(
        upstreams, ("compact-freeze", "sample-efficiency-batch", "sample-efficiency-report"),
    ):
        loaded = read_run(
            supplied.path, dataset=base["dataset"], protocol=base.to_dict(), stages=(stage,),
        )
        if loaded.manifest["artifact_id"] != supplied.manifest.get("artifact_id"):
            _fail("confirmation upstream artifact changed")
        verified.append(loaded)
    if (
        canonical(verified[0].read_json("freeze.json")) != canonical(freeze.to_dict())
        or verified[2].manifest.get("upstreams") != [_upstream_receipt(verified[1])]
    ):
        _fail("confirmation upstream semantic binding mismatch")
    return verified


def _upstream_receipt(run):
    return {
        "artifact_id": run.manifest["artifact_id"],
        "path": str(run.path),
        "stage": run.manifest["stage"],
    }


def _claim_content(scan, exclusion_receipts, *, base, overlay, freeze, freeze_artifact_id):
    return {
        "namespace": CLAIM_NAMESPACE,
        "population_id": scan.population_id,
        "input_sha256": scan.file_sha256,
        "base_research_protocol_sha256": base.digest,
        "sample_efficiency_protocol_sha256": overlay.digest,
        "compact_freeze_artifact_id": freeze_artifact_id,
        "compact_freeze_sha256": freeze.digest,
        "noninferiority": overlay["noninferiority"],
        "exclusion_receipts": exclusion_receipts,
    }


def _decode_payload(stream, scan, *, overlay, freeze):
    current = os.fstat(stream.fileno())
    current_stat = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
    if current_stat != scan.file_stat:
        _fail("confirmation input changed after claim")
    stream.seek(scan.payload_offset)
    payload_line = stream.readline(MAX_LINE_BYTES + 1)
    if (
        len(payload_line) > MAX_LINE_BYTES or not payload_line.endswith(b"\n")
        or b"\r" in payload_line or stream.readline(1)
    ):
        _fail("invalid confirmation payload grammar")
    payload = _strict_json(payload_line[:-1])
    if canonical(payload) != payload_line[:-1]:
        _fail("invalid canonical confirmation payload")
    differences = _validate_payload(payload, scan, overlay=overlay, freeze=freeze)
    stream.seek(0)
    after_digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        after_digest.update(chunk)
    after = os.fstat(stream.fileno())
    after_stat = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if after_stat != scan.file_stat or after_digest.hexdigest() != scan.file_sha256:
        _fail("confirmation input changed during payload decode")
    return payload, differences


def _result_value(scan, payload, differences, *, overlay, attempt_id, claim_key, claim_path):
    level = overlay["noninferiority"]["confidence_level"]
    lower, upper = np.quantile(
        differences, [(1 - level) / 2, (1 + level) / 2], method="linear",
    )
    satisfied = bool(upper <= overlay["noninferiority"]["delta_w68"])
    if scan.header["source_kind"] == "synthetic":
        status = "synthetic_rule_satisfied" if satisfied else "synthetic_rule_not_satisfied"
    else:
        status = "external_pending"
    result = {
        "schema_version": CONFIRMATION_SCHEMA,
        "attempt_id": attempt_id,
        "claim_key": claim_key,
        "claim_path": str(claim_path),
        "input_sha256": scan.file_sha256,
        "payload_id": payload["payload_id"],
        "population_id": scan.population_id,
        "validation_scope": payload["validation_scope"],
        "estimate": float(np.mean(differences)),
        "lower_ci": float(lower),
        "upper_ci": float(upper),
        "delta_w68": overlay["noninferiority"]["delta_w68"],
        "confidence_level": level,
        "ci_algorithm": overlay["noninferiority"]["ci_algorithm"],
        "bootstrap_replicates": len(differences),
        "rule_satisfied": satisfied,
        "status": status,
    }
    result["confirmation_id"] = digest_json(result)
    return result


def _claim(root, claim_value, *, repeat):
    directory = Path(root) / ".sample-efficiency-confirmation-claims"
    if directory.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(directory)):
        _fail("confirmation claim directory cannot be a link")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != Path(root).resolve():
        _fail("confirmation claim directory is outside the allowed root")
    path = directory / (claim_value["claim_key"] + ".json")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(claim_value))
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            directory_descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except FileExistsError:
        existing = read_json(path)
        static_keys = set(claim_value) - {"initial_attempt_id", "initial_output"}
        same_static_claim = (
            type(existing) is dict
            and set(existing) == set(claim_value)
            and all(existing.get(key) == claim_value[key] for key in static_keys)
            and type(existing.get("initial_attempt_id")) is str
            and type(existing.get("initial_output")) is str
        )
        if path.is_symlink() or not repeat or not same_static_claim:
            raise ResearchStateError(
                "existing confirmation claim requires identical explicit repeat",
                status="assessment_already_started",
            )
    return path


def publish_confirmation(
    output_dir, *, allowed_root, input_path, exclusion_identity_sets,
    base, overlay, freeze, freeze_artifact_id, upstreams=(), repeat=False,
):
    root = Path(allowed_root).resolve(strict=True)
    upstreams = _validate_upstreams(
        upstreams, freeze_artifact_id, base=base, freeze=freeze,
    )
    source = _regular_file(input_path)
    with source.open("rb") as stream:
        scan = scan_confirmation_handle(
            stream, base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_artifact_id,
        )
        excluded, exclusion_receipts = load_exclusion_identity_sets(
            exclusion_identity_sets, dataset=base["dataset"],
        )
        _validate_exclusion_coverage(
            scan, exclusion_receipts, excluded, overlay=overlay, freeze=freeze,
        )
        attempt_id = digest_json({
            "output": str(Path(output_dir).resolve()),
            "input_sha256": scan.file_sha256,
        })
        claim_content = _claim_content(
            scan, exclusion_receipts, base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_artifact_id,
        )
        claim_key = digest_json(claim_content)
        claim_value = dict(claim_content, claim_key=claim_key,
                           initial_attempt_id=attempt_id,
                           initial_output=str(Path(output_dir).resolve()))
        with ResearchRun(
            output_dir, allowed_root=root, stage=CONFIRMATION_STAGE,
            dataset=base["dataset"], protocol=base.to_dict(),
            upstreams=list(upstreams),
            context={
                "attempt_id": attempt_id, "claim_key": claim_key,
                "validation_scope": scan.header["source_kind"],
            },
        ) as run:
            run.write_json("preclaim.json", {
                "schema_version": PRECLAIM_SCHEMA,
                "attempt_id": attempt_id,
                "claim_key": claim_key,
                "population_id": scan.population_id,
                "input_sha256": scan.file_sha256,
                "size_bytes": scan.size_bytes,
                "exclusion_receipts": exclusion_receipts,
            })
            claim_path = _claim(root, claim_value, repeat=repeat)
            payload, differences = _decode_payload(stream, scan, overlay=overlay, freeze=freeze)
            result = _result_value(
                scan, payload, differences, overlay=overlay, attempt_id=attempt_id,
                claim_key=claim_key, claim_path=claim_path,
            )
            run.write_json("confirmation.json", result)
    if run.status != "complete":
        raise ResearchStateError(
            "confirmation attempt ended in a registered terminal state",
            status=run.status,
        )
    return read_confirmation(
        output_dir, allowed_root=root, input_path=input_path,
        exclusion_identity_sets=exclusion_identity_sets, base=base, overlay=overlay,
        freeze=freeze, freeze_artifact_id=freeze_artifact_id, upstreams=upstreams,
    )


def read_confirmation(
    path, *, allowed_root, input_path, exclusion_identity_sets, base, overlay,
    freeze, freeze_artifact_id, upstreams,
):
    root = Path(allowed_root).resolve(strict=True)
    upstreams = _validate_upstreams(
        upstreams, freeze_artifact_id, base=base, freeze=freeze,
    )
    run = read_run(
        path, dataset=base["dataset"], protocol=base.to_dict(),
        stages=(CONFIRMATION_STAGE,),
    )
    if set(run.manifest["files"]) != {
        "protocol.json", "preclaim.json", "confirmation.json",
    }:
        _fail("confirmation artifact file surface mismatch")
    if run.manifest.get("upstreams") != [_upstream_receipt(item) for item in upstreams]:
        _fail("confirmation direct-upstream binding mismatch")
    preclaim = run.read_json("preclaim.json")
    result = run.read_json("confirmation.json")
    result_keys = {
        "schema_version", "attempt_id", "claim_key", "claim_path", "input_sha256",
        "payload_id", "population_id", "validation_scope", "estimate", "lower_ci",
        "upper_ci", "delta_w68", "confidence_level", "ci_algorithm",
        "bootstrap_replicates", "rule_satisfied", "status", "confirmation_id",
    }
    if type(preclaim) is not dict or set(preclaim) != PRECLAIM_KEYS:
        _fail("invalid confirmation preclaim artifact")
    if type(result) is not dict or set(result) != result_keys:
        _fail("invalid confirmation artifact")
    source = _regular_file(input_path)
    with source.open("rb") as stream:
        scan = scan_confirmation_handle(
            stream, base=base, overlay=overlay, freeze=freeze,
            freeze_artifact_id=freeze_artifact_id,
        )
        excluded, exclusion_receipts = load_exclusion_identity_sets(
            exclusion_identity_sets, dataset=base["dataset"],
        )
        _validate_exclusion_coverage(
            scan, exclusion_receipts, excluded, overlay=overlay, freeze=freeze,
        )
        payload, differences = _decode_payload(stream, scan, overlay=overlay, freeze=freeze)
    attempt_id = digest_json({
        "output": str(Path(path).resolve()),
        "input_sha256": scan.file_sha256,
    })
    claim_content = _claim_content(
        scan, exclusion_receipts, base=base, overlay=overlay, freeze=freeze,
        freeze_artifact_id=freeze_artifact_id,
    )
    claim_key = digest_json(claim_content)
    claim_path = root / ".sample-efficiency-confirmation-claims" / f"{claim_key}.json"
    expected_preclaim = {
        "schema_version": PRECLAIM_SCHEMA,
        "attempt_id": attempt_id,
        "claim_key": claim_key,
        "population_id": scan.population_id,
        "input_sha256": scan.file_sha256,
        "size_bytes": scan.size_bytes,
        "exclusion_receipts": exclusion_receipts,
    }
    if canonical(preclaim) != canonical(expected_preclaim):
        _fail("confirmation preclaim semantic replay mismatch")
    actual_claim_path = _regular_file(claim_path)
    if Path(result["claim_path"]) != claim_path or actual_claim_path.resolve() != claim_path.resolve():
        _fail("confirmation claim location mismatch")
    claim = read_json(actual_claim_path)
    expected_claim_keys = set(claim_content) | {
        "claim_key", "initial_attempt_id", "initial_output",
    }
    if (
        type(claim) is not dict or set(claim) != expected_claim_keys
        or any(claim.get(key) != value for key, value in claim_content.items())
        or claim.get("claim_key") != claim_key
        or type(claim.get("initial_attempt_id")) is not str
        or type(claim.get("initial_output")) is not str
    ):
        _fail("confirmation claim receipt mismatch")
    initial_output = Path(claim["initial_output"])
    try:
        initial_output.resolve().relative_to(root)
    except ValueError:
        _fail("confirmation initial claim output is outside the allowed root")
    if claim["initial_attempt_id"] != digest_json({
        "output": str(initial_output.resolve()),
        "input_sha256": scan.file_sha256,
    }):
        _fail("confirmation initial claim attempt mismatch")
    expected_result = _result_value(
        scan, payload, differences, overlay=overlay, attempt_id=attempt_id,
        claim_key=claim_key, claim_path=claim_path,
    )
    if canonical(result) != canonical(expected_result):
        _fail("confirmation semantic replay mismatch")
    if run.manifest.get("context") != {
        "attempt_id": attempt_id,
        "claim_key": claim_key,
        "validation_scope": scan.header["source_kind"],
    }:
        _fail("confirmation manifest context mismatch")
    return run, result
