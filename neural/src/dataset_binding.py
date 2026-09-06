"""Scientific context layered on the standard-library download contract."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import yaml

from src.data_contract import DATASET_NAMES, parse_definition
from src.resource_seals import RESOURCE_HASHES

ROOT = Path(__file__).resolve().parents[1] / "config"


def _resource(name: str) -> bytes:
    payload = (ROOT / name).read_bytes()
    if hashlib.sha256(payload).hexdigest() != RESOURCE_HASHES[name]:
        raise ValueError(f"scientific resource hash changed: {name}")
    return payload


@dataclass(frozen=True)
class DatasetContext:
    name: str
    definition: bytes
    profile_payload: bytes
    science_payload: bytes

    @property
    def samples(self):
        return {member["role"]: member for member in json.loads(self.definition)["members"]}

    @property
    def profile(self):
        return yaml.safe_load(self.profile_payload)

    @property
    def science(self):
        return json.loads(self.science_payload)

    def snapshot(self):
        raw = json.loads(self.definition)
        return {
            "dataset_name": self.name,
            "definition_revision": raw["definition_revision"],
            "definition_sha256": hashlib.sha256(self.definition).hexdigest(),
            "release": raw["release"], "collection": raw["collection"],
            "profile_sha256": hashlib.sha256(self.profile_payload).hexdigest(),
            "science_sha256": hashlib.sha256(self.science_payload).hexdigest(),
            "event_identity_policy_id": self.science["event_identity_policy_id"],
            "samples": self.samples,
        }


def dataset_context(name: str) -> DatasetContext:
    from src.config import InputBindingError
    try:
        if name not in DATASET_NAMES:
            raise ValueError("unknown dataset")
        definition = (ROOT / "datasets" / f"{name}.json").read_bytes()
        parse_definition(definition, name)
        profile = "open_data_2020" if name == "atlas2020_4lep" else "release22"
        return DatasetContext(name, definition, _resource(f"profiles/{profile}.yaml"),
                              _resource("dataset_science_v1.json"))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise InputBindingError("dataset definition is invalid") from error


def validate_dataset_snapshot(snapshot, name: str | None = None) -> DatasetContext:
    from src.config import InputBindingError
    if not isinstance(snapshot, dict):
        raise InputBindingError("dataset binding missing; rebuild with --dataset")
    context = dataset_context(name if name is not None else snapshot.get("dataset_name"))
    if snapshot != context.snapshot():
        raise InputBindingError("dataset binding mismatch")
    return context


def validate_frame_identity(frame, snapshot) -> None:
    from src.config import InputBindingError
    from src.domain.splitting import event_split
    context = validate_dataset_snapshot(snapshot)
    members = {f"{role}_{m['dsid']}": m for role, m in context.samples.items()}
    if set(frame["source_sample"]) - set(members):
        raise InputBindingError("unregistered source sample")
    for row in frame[["source_sample", "source_file_id", "source_entry", "channelNumber",
                      "eventNumber", "event_group_id", "label", "split"]].itertuples(index=False):
        member = members[row.source_sample]
        if (row.channelNumber != member["dsid"] or row.label != member["label"]
                or row.source_file_id != member["file_id"] or row.source_entry < 0
                or row.source_entry >= member["entry_count"]
                or row.event_group_id != f"{row.channelNumber}:{row.eventNumber}"
                or row.split != event_split(row.eventNumber, row.channelNumber)):
            raise InputBindingError("sample/label/DSID/event identity binding changed")
    if frame.duplicated(["source_file_id", "source_entry"]).any():
        raise InputBindingError("source row identity is not unique")
