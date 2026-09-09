"""MC research export with identity-first reads and role-aware payload access."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import ResearchError, ResearchStateError
from .protocol import canonical, protocol_dict
from .representations import ENGINEERED19

ROLES = ("train", "validation", "calibration", "template", "assessment")
IDENTITY = ("event_id", "source_row_id", "event_group_id", "split", "dataset", "label", "role")


def role_for_group(group, protocol):
    p = protocol_dict(protocol)
    if not isinstance(group, str) or not group:
        raise ResearchError("event group identity missing")
    bucket = int.from_bytes(hashlib.sha256(f"h4l-role-v1:{group}".encode()).digest()[:8], "big") % 100
    boundary = 0
    for role in ROLES:
        boundary += round(p["roles"][role] * 100)
        if bucket < boundary:
            return role
    raise ResearchError("invalid role probabilities")


def assign_roles(frame, protocol):
    p = protocol_dict(protocol)
    result = frame.copy()
    if not (result["split"] == "development").all():
        raise ResearchError("research accepts development only")
    assigned = result.event_group_id.map(lambda g: role_for_group(g, p))
    if "role" in result and not (result.role == assigned).all():
        raise ResearchError("role differs from frozen group assignment")
    result["role"] = assigned
    result["sampling_probability"] = assigned.map(p["roles"]) * p["development_probability"]
    result["yield_weight"] = result.physical_weight / result.sampling_probability
    validate_role_isolation(result, p)
    return result


def validate_role_isolation(frame, protocol):
    p = protocol_dict(protocol)
    if not set(IDENTITY).issubset(frame):
        raise ResearchError("research identity columns missing")
    if frame[list(IDENTITY)].isna().any().any() or frame.source_row_id.duplicated().any() or frame.event_id.duplicated().any():
        raise ResearchError("missing or repeated row identity")
    if not (frame.dataset == p["dataset"]).all() or not (frame.split == "development").all():
        raise ResearchError("dataset/split boundary violation")
    if not set(frame.label).issubset({0, 1}) or not set(frame.role).issubset(ROLES):
        raise ResearchError("invalid role or label")
    if (frame.groupby("event_group_id")["role"].nunique() > 1).any() or (frame.groupby("event_group_id")["label"].nunique() > 1).any():
        raise ResearchError("event group crosses roles or labels")
    if not (frame.role == frame.event_group_id.map(lambda g: role_for_group(g, p))).all():
        raise ResearchError("role hash binding changed")


def grouped_statistics(frame, weight="yield_weight"):
    values = frame[weight].to_numpy(float)
    if not np.isfinite(values).all():
        raise ResearchError("weights must be finite")
    grouped = frame.groupby("event_group_id", sort=True)[weight].sum().to_numpy(float)
    signed, absolute = float(values.sum()), float(np.abs(values).sum())
    variance = float(grouped @ grouped)
    return {"rows": len(frame), "event_groups": len(grouped), "positive_sum": float(values[values > 0].sum()),
            "negative_sum": float(values[values < 0].sum()), "negative_fraction": float((values < 0).mean()) if len(values) else 0.,
            "signed_yield": signed, "sum_abs_weights": absolute, "sumw2": variance,
            "N_eff_signed": signed * signed / variance if variance else None,
            "N_eff_abs": absolute * absolute / variance if variance else None,
            "rho": abs(signed) / absolute if absolute else None,
            "status": "defined" if variance and absolute else "undefined_statistics"}


def audit_g0(frame, protocol):
    p = protocol_dict(protocol)
    validate_role_isolation(frame, p)
    # Assessment is never used to adapt support or thresholds.
    allowed = frame.loc[frame.role != "assessment"]
    records = []
    for role in ROLES[:-1]:
        for label in (0, 1):
            stats = grouped_statistics(allowed.loc[(allowed.role == role) & (allowed.label == label)])
            stats.update(role=role, label=label)
            stats["passes"] = (stats["signed_yield"] > 0 and stats["N_eff_signed"] is not None
                               and stats["N_eff_signed"] >= p["g0"]["min_neff_signed"]
                               and stats["rho"] >= p["g0"]["min_rho"])
            records.append(stats)
    return {"status": "passed" if all(x["passes"] for x in records) else "insufficient_statistics",
            "records": records, "assessment_used": False, "two_dimensional_templates_validated": False,
            "physics_sources_validated": False, "scope": "software_statistics_only"}


def write_research_data(frame, path, protocol):
    p = protocol_dict(protocol)
    validate_role_isolation(frame, p)
    kind = frame.attrs.get("source_kind")
    if kind not in {"synthetic", "controlled_mc"}:
        raise ResearchError("explicit synthetic or controlled MC provenance required")
    header = {"schema_version": "h4l-events-v1", "dataset": p["dataset"], "source_kind": kind,
              "mc_only": True, "protocol_digest": hashlib.sha256(canonical(p)).hexdigest(),
              "source_evidence": frame.attrs.get("source_evidence", {})}
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(header).decode() + "\n")
        for row in frame.to_dict(orient="records"):
            identity = {k: row.pop(k) for k in IDENTITY}
            stream.write(canonical(identity).decode() + "\t" + canonical(row).decode() + "\n")


def load_research_data(path, dataset, protocol, *, allow_assessment=False, assessment_freeze=None):
    p = protocol_dict(protocol)
    if allow_assessment:
        from .artifacts import digest_json
        if (not isinstance(assessment_freeze, dict) or assessment_freeze.get("status") != "frozen"
                or not assessment_freeze.get("evidence_id")
                or assessment_freeze.get("protocol_sha256") != digest_json(p)):
            raise ResearchError("assessment requires bound frozen-analysis evidence")
    rows, identities = [], []
    try:
        with Path(path).open(encoding="utf-8") as stream:
            header = json.loads(next(stream))
            if (header.get("schema_version") != "h4l-events-v1" or header.get("dataset") != dataset
                    or dataset != p["dataset"] or header.get("mc_only") is not True
                    or header.get("source_kind") not in {"synthetic", "controlled_mc"}
                    or header.get("protocol_digest") != hashlib.sha256(canonical(p)).hexdigest()):
                raise ResearchError("research data provenance/protocol mismatch")
            for line in stream:
                first, payload = line.rstrip("\n").split("\t", 1)
                identity = json.loads(first)
                if set(identity) != set(IDENTITY) or identity["split"] != "development" or identity["dataset"] != dataset:
                    raise ResearchError("non-development or malformed research identity")
                if identity["role"] != role_for_group(identity["event_group_id"], p):
                    raise ResearchError("role hash binding changed before payload access")
                identities.append(identity)
                if identity["role"] == "assessment" and not allow_assessment:
                    continue
                value = json.loads(payload)
                if set(value) & set(IDENTITY):
                    raise ResearchError("payload attempts identity override")
                rows.append(dict(identity, **value))
        validate_role_isolation(pd.DataFrame(identities, columns=IDENTITY), p)
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise ResearchStateError("no accessible research events", status="insufficient_statistics")
        for name in (*ENGINEERED19, "m4l", "y4l", "physical_weight", "sampling_probability", "yield_weight"):
            if name not in frame or not np.isfinite(frame[name].to_numpy(float)).all():
                raise ResearchError("research numerical columns missing or nonfinite")
        lo, hi = p["mass_window"]
        if not ((frame.m4l >= lo) & (frame.m4l < hi)).all():
            raise ResearchError("research mass support changed")
        expected = frame.role.map(p["roles"]) * p["development_probability"]
        if not np.allclose(frame.sampling_probability, expected, rtol=0, atol=1e-15) or not np.allclose(frame.yield_weight, frame.physical_weight / expected, rtol=1e-12, atol=1e-12):
            raise ResearchError("sampling/yield normalization changed")
        frame.attrs.update(source_kind=header["source_kind"], source_evidence=header["source_evidence"])
        return frame
    except (OSError, StopIteration, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ResearchError):
            raise
        raise ResearchError("invalid research data") from exc


def export_research_data(manifest_path, profile_path, protocol):
    """Read controlled MC. Uproot decodes payload only for development entries.

    ROOT baskets may contain neighboring test bytes; this is an array-decoding
    boundary, not a promise that storage reads never touch a mixed basket.
    Input SHA evidence is pre-existing acquisition evidence, never a test scan.
    """
    from src.dataset_binding import dataset_context
    from src.config import load_preprocess_protocol
    from src.domain.selection import SelectionConfig, select_event
    from src.domain.features import build_candidate_features
    from src.domain.angular5 import build_angular5
    from src.domain.splitting import event_split
    from src.domain.weights import physical_event_weight
    import uproot

    p = protocol_dict(protocol)
    context = dataset_context(p["dataset"])
    raw = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    if (raw.get("schema_version") != "h4l-root-input-v1" or raw.get("mc_only") is not True
            or raw.get("dataset") != p["dataset"] or set(raw.get("files", {})) != {"higgs", "zz"}
            or Path(profile_path).read_bytes() != context.profile_payload):
        raise ResearchError("controlled MC manifest/profile binding failure")
    sources = []
    for role, member in context.samples.items():
        item = raw["files"][role]
        source = Path(item["path"]).resolve()
        stat = source.stat()
        if (source.name != member["filename"] or source.parent.name != p["dataset"]
                or stat.st_size != member["size_bytes"] or item.get("sha256") != member["sha256"]
                or item.get("verified_size_bytes") != stat.st_size or item.get("verified_mtime_ns") != stat.st_mtime_ns):
            raise ResearchError("MC acquisition receipt or file metadata mismatch")
        sources.append((role, member, source))
    legacy = load_preprocess_protocol(Path(__file__).resolve().parents[2] / "config/preprocess_protocol_mass_window.yaml", dataset=p["dataset"])
    selection = SelectionConfig.from_mapping(dict(legacy.selection, m4l_window_gev=p["mass_window"]))
    profile = context.profile
    branches = profile["branches"]
    rows = []
    for process, member, source in sources:
        with uproot.open(source) as root:
            tree = root[profile["tree_name"]]
            if tree.num_entries != member["entry_count"] or not set(branches.values()).issubset(tree.keys()):
                raise ResearchError("MC tree schema/count mismatch")
            identities = tree.arrays([branches["eventNumber"], branches["channelNumber"]], library="np")
            if not np.all(identities[branches["channelNumber"]] == member["dsid"]):
                raise ResearchError("DSID differs before payload access")
            for entry in range(tree.num_entries):
                event_number = int(identities[branches["eventNumber"]][entry])
                channel = int(identities[branches["channelNumber"]][entry])
                if event_split(event_number, channel) == "test":
                    continue
                values = tree.arrays(list(branches.values()), entry_start=entry, entry_stop=entry + 1, library="ak")
                event = {name: values[branch][0].to_list() if hasattr(values[branch][0], "to_list") else values[branch][0] for name, branch in branches.items()}
                result = select_event(event, selection, profile["momentum_unit"])
                if not result.accepted:
                    continue
                c = result.candidate
                if sorted(np.abs(c.normalized.flavour).tolist()) != [11, 11, 13, 13]:
                    continue
                features = build_candidate_features(event, c)
                try:
                    features.update(build_angular5(c))
                except ValueError as exc:
                    raise ResearchStateError("invalid angular reconstruction", status="invalid_reconstruction") from exc
                vector = c.four_lepton
                if vector.energy <= abs(vector.pz):
                    raise ResearchError("undefined four-lepton rapidity")
                weight = physical_event_weight(mc_weight=float(event["mcWeight"]), luminosity_pb=p["luminosity_pb"], **context.science["normalization"][p["dataset"]][process])
                source_id = f"{member['file_id']}:{entry}"
                features.update(event_id=source_id, source_row_id=source_id, event_group_id=f"{channel}:{event_number}",
                    dataset=p["dataset"], split="development", label=member["label"], physical_weight=weight,
                    y4l=float(.5 * np.log((vector.energy + vector.pz) / (vector.energy - vector.pz))),
                    lep_pt=c.normalized.pt.tolist(), lep_eta=c.normalized.eta.tolist(), lep_phi=c.normalized.phi.tolist(),
                    lep_e=c.normalized.energy.tolist(), lep_charge=c.normalized.charge.tolist(), lep_type=c.normalized.flavour.tolist(),
                    pairing=[list(c.pairing.z1_indices), list(c.pairing.z2_indices)])
                rows.append(features)
    if not rows:
        raise ResearchStateError("no selected 2e2mu development events", status="insufficient_statistics")
    frame = assign_roles(pd.DataFrame(rows), p)
    frame.attrs.update(source_kind="controlled_mc", source_evidence={"dataset_snapshot": context.snapshot(),
                      "manifest": raw, "payload_access": "development_entries_only", "acquisition_hash_reverified": False})
    return frame
