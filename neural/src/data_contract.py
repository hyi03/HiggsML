"""Standard-library-only, pinned MC download definitions (not training approval)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import quote

DOWNLOAD_SCHEMA = "higgsml.download-definition.v1"
DATASET_NAMES = ("atlas2020_4lep", "atlas2025_exactly4lep")
# Revision and digest of reviewed, exact UTF-8 definition bytes.
APPROVED_DEFINITIONS: dict[str, tuple[int, str]] = {'atlas2020_4lep': (1, '6bbce80f1e47495ea880fc5af33952d9c8b5c82c12c73f447a1a14188d658a86'), 'atlas2025_exactly4lep': (1, '0d8bdf64b78b5055ba1a7156b658086fcd9089efffc88c9ef97a325f2017786d')}


@dataclass(frozen=True)
class Member:
    role: str
    label: int
    dsid: int
    file_id: str
    release: str
    collection: str
    record_url: str
    file_key: str
    download_url: str
    filename: str
    size_bytes: int
    sha256: str
    source_checksum: str
    tree: str
    entry_count: int


@dataclass(frozen=True)
class DatasetBinding:
    schema_version: str
    dataset_name: str
    definition_revision: int
    release: str
    collection: str
    mc_only: bool
    members: tuple[Member, ...]
    definition_sha256: str


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _keys(value: object, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("download definition has missing or unknown fields")


def parse_definition(raw: bytes, name: str) -> DatasetBinding:
    """Validate structure, identity and shipped digest; no unpinned mode."""
    if name not in DATASET_NAMES:
        raise ValueError(f"unknown dataset: {name}")
    value = json.loads(raw, object_pairs_hook=unique_object)
    _keys(value, {f.name for f in fields(DatasetBinding)} - {"definition_sha256"})
    release, collection, background, record = (
        ("2020", "4lep", 363490, "15005") if name == DATASET_NAMES[0]
        else ("2025", "exactly4lep", 700600, "atlas-93928")
    )
    if (value["schema_version"] != DOWNLOAD_SCHEMA
            or value["dataset_name"] != name
            or value["release"] != release or value["collection"] != collection
            or value["mc_only"] is not True
            or type(value["definition_revision"]) is not int
            or value["definition_revision"] < 1):
        raise ValueError("invalid dataset identity or download schema")
    if not isinstance(value["members"], list) or len(value["members"]) != 2:
        raise ValueError("a dataset requires exactly two MC members")
    members = []
    for item, role, label, dsid in zip(
        value["members"], ("higgs", "zz"), (1, 0), (345060, background), strict=True
    ):
        _keys(item, {f.name for f in fields(Member)})
        for field in fields(Member):
            expected_type = int if field.name in {"label", "dsid", "size_bytes", "entry_count"} else str
            if type(item[field.name]) is not expected_type:
                raise ValueError(f"invalid type: {field.name}")
        m = Member(**item)
        if (m.role, m.label, m.dsid, m.release, m.collection) != (role, label, dsid, release, collection):
            raise ValueError("MC member role/label/DSID/release/collection mismatch")
        if (m.filename != m.file_key or m.file_id != f"{name}:mc_{dsid}"
                or not re.fullmatch(r"[A-Za-z0-9_.-]+\.root", m.file_key)
                or m.record_url != f"https://opendata.cern.ch/record/{record}"
                or m.download_url != f"{m.record_url}/files/{quote(m.file_key, safe='._-')}"
                or m.size_bytes <= 0 or m.entry_count <= 0
                or not re.fullmatch(r"[0-9a-f]{64}", m.sha256)
                or not re.fullmatch(r"adler32:[0-9a-f]{8}", m.source_checksum)
                or m.tree != ("mini" if release == "2020" else "analysis")):
            raise ValueError("invalid MC file identity, path or metadata")
        prefix = "mc_" if release == "2020" else "ODEO_FEB2025_v0_exactly4lep_mc_"
        if not m.file_key.startswith(f"{prefix}{dsid}.") or not m.file_key.endswith(f".{collection}.root"):
            raise ValueError("file key does not match DSID/release/collection")
        members.append(m)
    if len({m.sha256 for m in members}) != 2 or len({m.file_id for m in members}) != 2:
        raise ValueError("duplicate member hash or file ID")
    digest = hashlib.sha256(raw).hexdigest()
    if APPROVED_DEFINITIONS.get(name) != (value["definition_revision"], digest):
        raise ValueError("download definition revision/SHA-256 is not approved")
    return DatasetBinding(**dict(value, members=tuple(members)), definition_sha256=digest)


def load_dataset(name: str) -> DatasetBinding:
    """Load only a shipped name, independently of cwd and other src packages."""
    if name not in DATASET_NAMES:
        raise ValueError(f"unknown dataset: {name}")
    path = Path(__file__).resolve().parents[1] / "config" / "datasets" / f"{name}.json"
    return parse_definition(path.read_bytes(), name)
