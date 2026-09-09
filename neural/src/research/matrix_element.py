"""External ME interchange; no substitute probability model is supplied."""
import hashlib
import re
import numpy as np
import pandas as pd

from .errors import ResearchError, ResearchStateError
from .protocol import canonical, protocol_dict


def _digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def export_me_inputs(frame, protocol, backend, process):
    p = protocol_dict(protocol)
    if not isinstance(backend, dict) or set(backend) != {"name", "version", "configuration_sha256"} or not all(backend.values()):
        raise ResearchError("exact ME backend/version/configuration required")
    if not isinstance(process, dict) or set(process) != {"signal", "background", "pdf", "approximation"} or not all(process.values()):
        raise ResearchError("exact ME process/PDF/approximation required")
    if frame.event_id.duplicated().any() or not (frame.split == "development").all():
        raise ResearchError("ME export requires unique development rows")
    events = []
    for row in frame.to_dict(orient="records"):
        item = {key: row[key] for key in ("event_id", "event_group_id", "lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type", "pairing")}
        arrays = [item[key] for key in ("lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type")]
        if any(len(v) != 4 for v in arrays) or not np.isfinite(np.asarray(arrays, float)).all():
            raise ResearchError("ME requires four finite reconstructed leptons")
        if sorted(np.abs(item["lep_type"]).tolist()) != [11, 11, 13, 13] or sorted(sum(item["pairing"], [])) != [0, 1, 2, 3]:
            raise ResearchError("ME final state/pairing mismatch")
        item["input_digest"] = _digest(item)
        events.append(item)
    result = {"schema_version": "h4l-me-input-v1", "dataset": p["dataset"], "protocol_digest": _digest(p),
              "probability_definition": "kinematic_decay7_at_fixed_m4l_no_mass_pdf",
              "units": "GeV", "ordering": "descending_pt_stable", "backend": backend, "process": process, "events": events}
    result["input_digest"] = _digest(result)
    return result


def import_me_results(inputs, results, reference, protocol):
    p = protocol_dict(protocol)
    if not reference:
        raise ResearchStateError("independent ME reference is missing", status="blocked_missing_reference")
    if inputs.get("input_digest") != _digest({k: v for k, v in inputs.items() if k != "input_digest"}):
        raise ResearchError("ME input digest mismatch")
    if inputs.get("protocol_digest") != _digest(p):
        raise ResearchError("ME protocol mismatch")
    if inputs.get("probability_definition") != "kinematic_decay7_at_fixed_m4l_no_mass_pdf":
        raise ResearchError("ME must use kinematic decay inputs at fixed mass without a mass PDF")
    for key in ("backend", "process", "units", "probability_definition"):
        if results.get(key) != inputs[key] or reference.get(key) != inputs[key]:
            raise ResearchError(f"ME {key} mismatch")
    if (results.get("schema_version") != "h4l-me-output-v1" or results.get("input_digest") != inputs["input_digest"]
            or reference.get("status") != "validated" or not reference.get("evidence_id")):
        raise ResearchError("ME result/reference binding invalid")
    adapter_digest = results.get("adapter_sha256")
    if (not isinstance(adapter_digest,str) or not re.fullmatch(r"[0-9a-f]{64}",adapter_digest)
            or reference.get("adapter_sha256") != adapter_digest):
        raise ResearchError("ME independent reference must bind the exact executed adapter SHA256")
    checks = reference.get("checks", [])
    if not checks:
        raise ResearchStateError("independent numerical ME checks missing", status="blocked_missing_reference")
    for check in checks:
        # Evidence includes the exact independent input and both probability pairs.
        if not check.get("event_input") or check.get("input_digest") != _digest(check["event_input"]):
            raise ResearchError("ME independent reference event binding invalid")
        if check.get("adapter_sha256") != adapter_digest:
            raise ResearchError("ME numerical check adapter SHA256 mismatch")
        expected, actual = np.asarray(check["expected"], float), np.asarray(check["actual"], float)
        if (expected.shape != (2,) or actual.shape != (2,) or not np.isfinite([expected, actual]).all()
                or (expected < 0).any() or (actual < 0).any()
                or not np.allclose(expected, actual, rtol=p["matrix_element"]["reference_rtol"], atol=p["matrix_element"]["reference_atol"])):
            raise ResearchError("ME independent numerical reference failed")
    expected = {e["event_id"]: e for e in inputs["events"]}
    records, seen = [], set()
    for row in results.get("events", []):
        event_id = row.get("event_id")
        if event_id not in expected or event_id in seen or row.get("input_digest") != expected[event_id]["input_digest"]:
            raise ResearchError("ME row missing/duplicate/input mismatch")
        probabilities = np.asarray([row["p_signal"], row["p_background"]], float)
        if not np.isfinite(probabilities).all() or (probabilities < 0).any() or probabilities.sum() <= 0:
            raise ResearchError("ME probabilities invalid")
        seen.add(event_id)
        records.append({"event_id": event_id, "me_score": float(probabilities[0] / probabilities.sum()),
                        "p_signal": float(probabilities[0]), "p_background": float(probabilities[1])})
    if seen != set(expected):
        raise ResearchError("ME output does not cover every input event")
    return pd.DataFrame(records).set_index("event_id").loc[list(expected)].reset_index()
