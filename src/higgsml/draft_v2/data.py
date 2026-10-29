"""Identity-first three-role envelopes and receipt-bound all-MC preparation."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from higgsml.artifacts import digest_json, read_json
from higgsml.data import IDENTITY, iter_records, population_digest, _export_selected_research_data
from higgsml.dataset_binding import dataset_context
from higgsml.errors import ResearchError
from higgsml.modeling.representations import ENGINEERED19
from higgsml.protocol import canonical
from higgsml.draft_v2.protocol import DEFAULT_PROTOCOL, ROLES, validate_protocol


def role_for_group(group):
    if not isinstance(group, str) or not group:
        raise ResearchError("Missing physical event group")
    bucket = int.from_bytes(hashlib.sha256(
        f"h4l-draft-v2-role-v1:{group}".encode()).digest()[:8], "big") % 100
    return "train" if bucket < 60 else "validation" if bucket < 80 else "evaluation"


def validate_identities(frame, protocol):
    if frame.empty or not set(IDENTITY) <= set(frame):
        raise ResearchError("Missing draft-v2 identity envelope")
    if frame[list(IDENTITY)].isna().any().any():
        raise ResearchError("Null identity")
    if frame.event_id.duplicated().any() or frame.source_row_id.duplicated().any():
        raise ResearchError("Duplicate event/source row")
    if (not (frame.dataset == protocol['dataset']).all() or not (frame.split == 'exploratory').all()
            or not frame.label.isin([0, 1]).all() or not frame.role.isin(ROLES).all()):
        raise ResearchError("Wrong dataset/population/label/role")
    if not (frame.role == frame.event_group_id.map(role_for_group)).all():
        raise ResearchError("Draft-v2 role hash mismatch")
    if (frame.groupby('event_group_id').label.nunique() > 1).any():
        raise ResearchError("Physical group crosses labels")


def assign_roles(frame, protocol):
    validate_protocol(protocol)
    result = frame.copy()
    # Existing role-bearing artifacts are never silently relabelled.
    if 'role' in result or 'sampling_probability' in result or 'yield_weight' in result:
        raise ResearchError("Draft-v2 requires newly reconstructed, unassigned events")
    if not (result['split'] == 'exploratory').all():
        raise ResearchError("Draft-v2 requires all-MC source population")
    result['role'] = result.event_group_id.map(role_for_group)
    result['sampling_probability'] = result.role.map(protocol['roles'])
    result['yield_weight'] = result.physical_weight / result.sampling_probability
    validate_identities(result, protocol)
    validate_values(result, protocol)
    return result


def validate_values(frame, protocol):
    columns = [*ENGINEERED19, 'm4l', 'physical_weight', 'yield_weight', 'sampling_probability']
    if not set(columns) <= set(frame) or not np.isfinite(frame[columns].to_numpy(float)).all():
        raise ResearchError("Missing/nonfinite draft-v2 values")
    if not ((frame.m4l >= 105.) & (frame.m4l < 140.)).all():
        raise ResearchError("Mass outside half-open draft-v2 support")
    probability = frame.role.map(protocol['roles']).to_numpy(float)
    if (not np.allclose(frame.sampling_probability, probability, rtol=0, atol=1e-15)
            or not np.allclose(frame.yield_weight, frame.physical_weight / probability,
                               rtol=1e-12, atol=1e-12)):
        raise ResearchError("Draft-v2 sampling/yield normalization mismatch")


def root_manifest(receipt_path, protocol):
    """Use acquisition receipts, not a new scan or hash of ROOT payload."""
    path = Path(receipt_path).resolve()
    receipt = read_json(path)
    context = dataset_context(protocol['dataset'])
    if (receipt.get('schema_version') != 'higgsml.download-receipt.v1'
            or receipt.get('status') != 'complete' or receipt.get('mc_only') is not True
            or receipt.get('dataset_name') != protocol['dataset']):
        raise ResearchError("Complete controlled-2020-MC acquisition receipt required")
    members = receipt.get('members', [])
    if (len(members) != 2 or any(not isinstance(item, dict) for item in members)
            or {item.get('role') for item in members} != {'higgs', 'zz'}):
        raise ResearchError("Exactly the two contracted MC members are required")
    files = {}
    for item in members:
        member = context.samples[item['role']]
        source = path.parent / member['filename']
        if (item.get('filename') != member['filename'] or source.is_symlink()
                or not source.is_file() or source.parent.name != protocol['dataset']):
            raise ResearchError("MC member path/identity mismatch")
        stat = source.stat()
        if (stat.st_size != member['size_bytes']
                or item.get('size_bytes') != stat.st_size or item.get('actual_size_bytes') != stat.st_size
                or item.get('sha256') != member['sha256'] or item.get('actual_sha256') != member['sha256']):
            raise ResearchError("MC acquisition size/hash evidence mismatch")
        files[item['role']] = dict(path=str(source), sha256=member['sha256'],
            verified_size_bytes=stat.st_size, verified_mtime_ns=stat.st_mtime_ns)
    return dict(schema_version='h4l-root-input-v1', dataset=protocol['dataset'], mc_only=True, files=files)


def reconstruct(manifest_path, protocol, *, metrics=None, max_entries=4096, root_threads=1,
                progress=True):
    # The shared extractor stops before role assignment. The old export still
    # applies its unchanged five-role assignment and historical source mask.
    if progress and metrics is None:
        metrics = {}
    frame = _export_selected_research_data(
        manifest_path, DEFAULT_PROTOCOL.parent.parent / 'profiles/open_data_2020.yaml', protocol,
        metrics=metrics, max_entries=max_entries, root_threads=root_threads,
        show_prepare_progress=progress)
    began = time.perf_counter()
    frame = assign_roles(frame, protocol)
    if metrics is not None:
        metrics['role_assignment_seconds'] = time.perf_counter() - began
    return frame


def write_events(frame, path, protocol):
    validate_identities(frame, protocol)
    validate_values(frame, protocol)
    kind = frame.attrs.get('source_kind')
    if kind not in {'synthetic', 'controlled_mc'}:
        raise ResearchError("Explicit source kind required")
    header = dict(schema_version='h4l-draft-v2-events-v1', source_kind=kind, mc_only=True,
                  dataset=protocol['dataset'], protocol_sha256=digest_json(protocol),
                  source_evidence=frame.attrs.get('source_evidence', {}))
    with Path(path).open('xb') as stream:
        stream.write(canonical(header) + b'\n')
        for row in iter_records(frame):
            identity = {key: row.pop(key) for key in IDENTITY}
            stream.write(canonical(identity) + b'\t' + canonical(row) + b'\n')
    groups = set(zip(frame.event_group_id, frame.label, frame.split, frame.dataset))
    return population_digest(groups, protocol['dataset'])


def read_events(path, protocol, *, evaluation=False, freeze=None, prepared_id=None):
    if evaluation and (not isinstance(freeze, dict) or freeze.get('status') != 'frozen'
            or freeze.get('protocol_sha256') != digest_json(protocol)
            or freeze.get('prepared_artifact_id') != prepared_id
            or freeze.get('freeze_id') != digest_json({k: v for k, v in freeze.items() if k != 'freeze_id'})):
        raise ResearchError("Evaluation requires the bound draft-v2 freeze")
    rows, identities = [], []
    try:
        with Path(path).open(encoding='utf-8') as stream:
            header = json.loads(next(stream))
            if (header.get('schema_version') != 'h4l-draft-v2-events-v1'
                    or header.get('protocol_sha256') != digest_json(protocol)
                    or header.get('dataset') != protocol['dataset'] or header.get('mc_only') is not True
                    or header.get('source_kind') not in {'synthetic', 'controlled_mc'}):
                raise ResearchError("Invalid draft-v2 event provenance")
            for line in stream:
                envelope, payload = line.rstrip('\n').split('\t', 1)
                identity = json.loads(envelope)
                if (set(identity) != set(IDENTITY) or identity['role'] != role_for_group(identity['event_group_id'])
                        or identity['dataset'] != protocol['dataset'] or identity['split'] != 'exploratory'):
                    raise ResearchError("Invalid role/population before payload access")
                identities.append(identity)
                if (identity['role'] == 'evaluation') != evaluation:
                    continue  # Deliberately before JSON payload decoding.
                value = json.loads(payload)
                if not isinstance(value, dict) or set(value) & set(IDENTITY):
                    raise ResearchError("Payload overrides identity")
                rows.append({**identity, **value})
        all_ids = pd.DataFrame(identities)
        validate_identities(all_ids, protocol)
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise ResearchError("No accessible draft-v2 events")
        validate_values(frame, protocol)
        frame.attrs.update(source_kind=header['source_kind'], source_evidence=header['source_evidence'],
            population_id=population_digest(set(zip(all_ids.event_group_id, all_ids.label,
                                                   all_ids.split, all_ids.dataset)), protocol['dataset']))
        return frame
    except (OSError, StopIteration, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ResearchError):
            raise
        raise ResearchError("Invalid draft-v2 event envelope") from error
