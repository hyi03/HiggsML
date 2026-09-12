"""Deterministic train-group subset plans; no model or assessment payload access."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .artifacts import LoadedRun, ResearchRun, digest_json, read_run
from .data import IDENTITY, population_digest, role_for_group
from .errors import ResearchError
from .protocol import ResearchProtocol, canonical
from .sample_efficiency_protocol import (
    SampleEfficiencyProtocol,
    load_compact_candidate_freeze,
)


PLAN_SCHEMA = "h4l-training-subset-plan-v1"
MEMBERSHIP_SCHEMA = "h4l-training-subset-membership-v1"
LEDGER_SCHEMA = "h4l-training-subset-ledger-v1"


def _fail(message):
    raise ResearchError(message, status="training_subset_binding_mismatch")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON key in training subset input")
        result[key] = value
    return result


def _reject_constant(value):
    _fail(f"nonfinite JSON constant in training subset input: {value}")


def _loads_strict(value):
    return json.loads(value, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _reload_input(run, base, stage, name):
    if not isinstance(run, LoadedRun) or not isinstance(base, ResearchProtocol):
        _fail(f"validated {name}/base inputs required")
    try:
        return read_run(run.path, dataset=base["dataset"], protocol=base.to_dict(), stages=(stage,))
    except ResearchError as exc:
        raise ResearchError(f"invalid {name} run", status="training_subset_binding_mismatch") from exc


def _read_train_rows(prepared: LoadedRun, base: ResearchProtocol):
    path = prepared.file("events.jsonl")
    protocol = base.to_dict()
    lines = []
    identities = []
    roles = {}
    population = set()
    try:
        with path.open(encoding="utf-8") as stream:
            header_line = next(stream).rstrip("\n")
            header = _loads_strict(header_line)
            expected_header = {"schema_version", "dataset", "source_kind", "mc_only",
                               "protocol_digest", "source_evidence"}
            if (set(header) != expected_header or canonical(header).decode() != header_line
                    or header["schema_version"] != "h4l-events-v1"
                    or header["dataset"] != protocol["dataset"] or header["mc_only"] is not True
                    or header["source_kind"] not in {"synthetic", "controlled_mc"}
                    or header["protocol_digest"] != base.digest):
                _fail("prepared events header binding mismatch")
            expected_split = "exploratory" if protocol.get("source_population") == "all_mc" else "development"
            seen_rows = set()
            seen_events = set()
            for line_number, line in enumerate(stream, 2):
                identity_text, payload_text = line.rstrip("\n").split("\t", 1)
                identity = _loads_strict(identity_text)
                if set(identity) != set(IDENTITY) or canonical(identity).decode() != identity_text:
                    _fail(f"noncanonical prepared identity at line {line_number}")
                if (identity["dataset"] != protocol["dataset"]
                        or identity["split"] != expected_split
                        or type(identity["label"]) is not int or identity["label"] not in (0, 1)):
                    _fail("prepared identity population mismatch")
                for key in ("event_id", "source_row_id", "event_group_id", "role"):
                    if type(identity[key]) is not str or not identity[key]:
                        _fail("prepared identity text field invalid")
                if identity["source_row_id"] in seen_rows:
                    _fail("duplicate prepared source row identity")
                if identity["event_id"] in seen_events:
                    _fail("duplicate prepared event identity")
                seen_rows.add(identity["source_row_id"])
                seen_events.add(identity["event_id"])
                group = identity["event_group_id"]
                expected_role = roles.setdefault(group, role_for_group(group, protocol))
                if identity["role"] != expected_role:
                    _fail("event group role hash mismatch")
                identities.append(identity)
                population.add((group, identity["label"], identity["split"], identity["dataset"]))
                lines.append((identity, payload_text))
    except ResearchError:
        raise
    except (OSError, StopIteration, ValueError, TypeError) as exc:
        raise ResearchError("invalid prepared events stream", status="training_subset_binding_mismatch") from exc
    group_keys = {}
    for identity in identities:
        key = identity["event_group_id"]
        pair = (identity["role"], identity["label"])
        if key in group_keys and group_keys[key] != pair:
            _fail("event group has mixed role or label")
        group_keys[key] = pair
    identities.sort(key=lambda item: canonical([item[k] for k in IDENTITY]))
    identity_digest = hashlib.sha256(canonical(identities)).hexdigest()
    stats = {}
    # Decode only payloads whose role was validated as train in the first pass.
    lines.sort(key=lambda item: canonical([item[0][k] for k in IDENTITY]))
    for identity, payload_text in lines:
        if identity["role"] != "train":
            continue
        try:
            payload = _loads_strict(payload_text)
            if set(payload) & set(IDENTITY) or not {"physical_weight", "m4l"} <= set(payload):
                _fail("train payload missing summary fields or overrides identity")
            weight, mass = payload["physical_weight"], payload["m4l"]
            if type(weight) not in (int, float) or type(mass) not in (int, float) or not math.isfinite(weight) or not math.isfinite(mass):
                _fail("train summary value is nonfinite")
        except ResearchError:
            raise
        except (ValueError, TypeError) as exc:
            raise ResearchError("invalid train payload", status="training_subset_binding_mismatch") from exc
        group = identity["event_group_id"]
        item = stats.setdefault(group, {"label": identity["label"], "rows": 0, "weight": 0.0,
                                        "mass_min": float(mass), "mass_max": float(mass)})
        item["rows"] += 1
        item["weight"] += float(weight)
        item["mass_min"] = min(item["mass_min"], float(mass))
        item["mass_max"] = max(item["mass_max"], float(mass))
    return stats, identity_digest, population_digest(population, protocol["dataset"])


def _summary_record(chosen, *, label=None):
    weights = [x["weight"] for x in chosen]
    sum_abs = sum(abs(x) for x in weights)
    sumw2 = sum(x * x for x in weights)
    record = {"group_count": len(chosen), "row_count": sum(x["rows"] for x in chosen),
              "sum_signed_weight": sum(weights), "sum_abs_weight": sum_abs, "sumw2": sumw2,
              "neff_abs": sum_abs * sum_abs / sumw2 if sumw2 > 0 else None,
              "m4l_min": min((x["mass_min"] for x in chosen), default=None),
              "m4l_max": max((x["mass_max"] for x in chosen), default=None)}
    if label is not None:
        record = {"label": label, **record}
    return record


def _summary(groups, group_stats):
    chosen = [group_stats[group] for group in groups]
    return ([_summary_record([item for item in chosen if item["label"] == label], label=label)
             for label in (0, 1)],
            _summary_record(chosen))


def build_training_subset_payloads(prepared, base, overlay):
    if not isinstance(base, ResearchProtocol) or not isinstance(overlay, SampleEfficiencyProtocol):
        _fail("validated prepared/base/overlay inputs required")
    prepared = _reload_input(prepared, base, "prepare", "prepared")
    raw = overlay.to_dict()
    if prepared.manifest.get("stage") != "prepare" or prepared.manifest.get("artifact_id") != raw["prepared_artifact_id"]:
        _fail("prepared artifact binding mismatch")
    stats, identity_digest, population_id = _read_train_rows(prepared, base)
    if population_id != raw["population_id"]:
        _fail("prepared population binding mismatch")
    memberships, subset_entries, ledger = [], {}, []
    for draw in raw["sample_draw_seeds"]:
        ordered = {label: sorted((g for g, item in stats.items() if item["label"] == label), key=lambda g: (hashlib.sha256(canonical([
            base.digest, raw["prepared_artifact_id"], raw["subset_algorithm"]["id"], draw, label, g])).hexdigest(), g))
            for label in (0, 1)}
        for fraction in raw["sample_fractions"]:
            fraction_value = 1.0 if fraction == 1.0 else float(fraction)
            draw_or_full = "full" if fraction_value == 1.0 else draw
            key = (draw_or_full, fraction_value)
            if key not in subset_entries:
                groups = sorted(g for label in (0, 1) for g in (ordered[label] if fraction_value == 1.0 else
                    ordered[label][:math.floor(fraction_value * len(ordered[label]))]))
                records = [{"draw_or_full": draw_or_full, "fraction": fraction_value,
                            "label": stats[g]["label"], "event_group_id": g} for g in groups]
                records.sort(key=lambda x: canonical([x["draw_or_full"], x["fraction"], x["label"], x["event_group_id"]]))
                membership_digest = hashlib.sha256(canonical(records)).hexdigest()
                subset_id = hashlib.sha256(canonical([overlay.digest, raw["prepared_artifact_id"], draw_or_full,
                                                       fraction_value, membership_digest])).hexdigest()
                summary, summary_total = _summary(groups, stats)
                cfg = raw["subset_algorithm"]
                usable = all(x["group_count"] >= cfg["min_groups_per_label"] and x["sum_abs_weight"] > 0
                             and x["neff_abs"] is not None and x["neff_abs"] >= cfg["min_effective_count"] for x in summary)
                subset_entries[key] = {"subset_id": subset_id, "draw_or_full": draw_or_full,
                    "fraction": fraction_value, "membership_digest": membership_digest,
                    "status": "planned" if usable else "training_subset_insufficient_statistics",
                    "summary_by_label": summary, "summary_total": summary_total}
                memberships.extend(records)
            entry = subset_entries[key]
            ledger.append({"alias_id": hashlib.sha256(canonical([entry["subset_id"], draw, fraction_value])).hexdigest(),
                           "sample_draw_seed": draw, "fraction": fraction_value, "subset_id": entry["subset_id"],
                           "membership_digest": entry["membership_digest"], "status": entry["status"]})
    memberships.sort(key=lambda x: canonical([x["draw_or_full"], x["fraction"], x["label"], x["event_group_id"]]))
    plan = {"schema_version": PLAN_SCHEMA, "base_research_protocol_sha256": base.digest,
            "sample_efficiency_protocol_sha256": overlay.digest, "prepared_artifact_id": raw["prepared_artifact_id"],
            "population_id": population_id, "compact_candidate_freeze_artifact_id": raw["compact_candidate_freeze_artifact_id"],
            "compact_candidate_freeze_sha256": raw["compact_candidate_freeze_sha256"], "identity_digest": identity_digest,
            "subsets": sorted(subset_entries.values(), key=lambda x: canonical([x["draw_or_full"], x["fraction"]]))}
    return plan, memberships, {"schema_version": LEDGER_SCHEMA, "cells": ledger}


def publish_training_subsets(output_dir, *, allowed_root, prepared, freeze_run, base, overlay):
    prepared = _reload_input(prepared, base, "prepare", "prepared")
    freeze_run = _reload_input(freeze_run, base, "compact-freeze", "compact-freeze")
    raw = overlay.to_dict()
    if freeze_run.manifest.get("artifact_id") != raw["compact_candidate_freeze_artifact_id"]:
        _fail("compact freeze artifact binding mismatch")
    freeze = load_compact_candidate_freeze(freeze_run.file("freeze.json"), base_protocol=base)
    if freeze.digest != raw["compact_candidate_freeze_sha256"]:
        _fail("compact freeze payload binding mismatch")
    plan, memberships, ledger = build_training_subset_payloads(prepared, base, overlay)
    with ResearchRun(output_dir, allowed_root=allowed_root, stage="training-subsets",
                     dataset=base["dataset"], protocol=base.to_dict(), upstreams=[prepared, freeze_run],
                     context={"sample_efficiency_protocol_sha256": overlay.digest}) as run:
        run.write_json("sample-efficiency-protocol.json", overlay.to_dict())
        run.write_json("training-subsets.json", plan)
        member_path = run.path / "training-subset-membership.jsonl"
        with member_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical({"schema_version": MEMBERSHIP_SCHEMA}).decode() + "\n")
            for record in memberships:
                stream.write(canonical(record).decode() + "\n")
        run.register_file(member_path.name)
        run.write_json("training-subset-ledger.json", ledger)
    return read_run(output_dir, dataset=base["dataset"], protocol=base.to_dict(), stages=("training-subsets",))


def read_training_subsets(run, *, prepared, freeze_run, base, overlay):
    prepared = _reload_input(prepared, base, "prepare", "prepared")
    freeze_run = _reload_input(freeze_run, base, "compact-freeze", "compact-freeze")
    run_path = run.path if isinstance(run, LoadedRun) else run
    try:
        run = read_run(run_path, dataset=base["dataset"], protocol=base.to_dict(), stages=("training-subsets",))
    except ResearchError as exc:
        raise ResearchError("invalid training-subsets run", status="training_subset_binding_mismatch") from exc
    upstreams = {(x.get("stage"), x.get("artifact_id")) for x in run.manifest.get("upstreams", [])}
    if upstreams != {("prepare", prepared.manifest["artifact_id"]), ("compact-freeze", freeze_run.manifest["artifact_id"])}:
        _fail("training subset upstream binding mismatch")
    freeze = load_compact_candidate_freeze(freeze_run.file("freeze.json"), base_protocol=base)
    if (freeze_run.manifest["artifact_id"] != overlay["compact_candidate_freeze_artifact_id"]
            or freeze.digest != overlay["compact_candidate_freeze_sha256"]):
        _fail("training subset compact freeze binding mismatch")
    if run.read_json("sample-efficiency-protocol.json") != overlay.to_dict():
        _fail("training subset overlay snapshot mismatch")
    expected_plan, expected_members, expected_ledger = build_training_subset_payloads(prepared, base, overlay)
    if run.read_json("training-subsets.json") != expected_plan or run.read_json("training-subset-ledger.json") != expected_ledger:
        _fail("training subset plan or ledger recomputation mismatch")
    try:
        payload = run.file("training-subset-membership.jsonl").read_bytes()
        if not payload.endswith(b"\n") or b"\r" in payload:
            _fail("noncanonical training subset membership line endings")
        raw_lines = payload[:-1].split(b"\n")
        if not raw_lines or any(not line for line in raw_lines):
            _fail("invalid training subset membership line count")
        parsed = [_loads_strict(line.decode("utf-8")) for line in raw_lines]
        if any(canonical(value) != line for value, line in zip(parsed, raw_lines)):
            _fail("noncanonical training subset membership record")
        header, members = parsed[0], parsed[1:]
    except ResearchError:
        raise
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise ResearchError("invalid training subset membership", status="training_subset_binding_mismatch") from exc
    if header != {"schema_version": MEMBERSHIP_SCHEMA} or members != expected_members:
        _fail("training subset membership recomputation mismatch")
    return expected_plan, expected_members, expected_ledger
