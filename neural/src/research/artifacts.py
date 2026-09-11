"""Bound, immutable stage artifacts using the repository's run transaction."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from src.artifacts.manifest import canonical_json_bytes, sha256_file, software_record
from src.artifacts.transaction import RunTransaction
from src.research.errors import ResearchError, ResearchStateError


def digest_json(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _filename(name: str) -> str:
    if not isinstance(name, str) or not name or name in {".", ".."} or any(c in name for c in '/\\:'):
        raise ResearchError("artifact filename must be a single local filename")
    return name


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, ValueError) as error:
        raise ResearchError(f"invalid JSON artifact: {path.name}") from error


@dataclass(frozen=True)
class LoadedRun:
    path: Path
    manifest: dict

    def file(self, name: str) -> Path:
        name = _filename(name)
        receipt = self.manifest["files"].get(name)
        if not isinstance(receipt, dict):
            raise ResearchError(f"unbound artifact file: {name}")
        path = self.path / name
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self.path.resolve():
            raise ResearchError(f"invalid artifact file: {name}")
        if sha256_file(path) != receipt.get("sha256") or path.stat().st_size != receipt.get("size_bytes"):
            raise ResearchError(f"artifact digest mismatch: {name}")
        return path

    def read_json(self, name: str) -> Any:
        return read_json(self.file(name))


def read_run(path: str | Path, *, dataset: str, protocol: dict,
             stages: tuple[str, ...] | None = None, allow_terminal: bool = False) -> LoadedRun:
    root = Path(path)
    if root.is_symlink() or (root / "manifest.json").is_symlink():
        raise ResearchError("research run cannot be a symlink")
    manifest = read_json(root / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "research-run-v1":
        raise ResearchError("invalid research artifact schema")
    if manifest.get("dataset") != dataset:
        raise ResearchError("research artifact dataset mismatch")
    if manifest.get("protocol_sha256") != digest_json(protocol):
        raise ResearchError("research artifact protocol mismatch")
    identity = dict(manifest)
    artifact_id = identity.pop("artifact_id", None)
    if artifact_id != digest_json(identity):
        raise ResearchError("research manifest digest mismatch")
    if not isinstance(manifest.get("files"), dict):
        raise ResearchError("invalid research artifact file index")
    if stages is not None and manifest.get("stage") not in stages:
        raise ResearchError("wrong upstream research stage")
    if not allow_terminal and manifest.get("status") != "complete":
        raise ResearchError(f"research artifact not usable: {manifest.get('status')}")
    loaded = LoadedRun(root.resolve(), manifest)
    if loaded.read_json("protocol.json") != protocol:
        raise ResearchError("research protocol snapshot mismatch")
    return loaded


class ResearchRun:
    def __init__(self, run_dir: str | Path, *, allowed_root: str | Path,
                 stage: str, dataset: str, protocol: dict,
                 upstreams: list[LoadedRun] | None = None, seed: int | None = None,
                 context: dict | None = None):
        self.transaction = RunTransaction(run_dir, allowed_root=allowed_root,
                                          safe_failure_stage=f"research:{stage}")
        self.path = self.transaction.path
        self.protocol = protocol
        self.status = "complete"
        self._stream_verified_files: set[str] = set()
        self.manifest = {
            "schema_version": "research-run-v1", "stage": stage, "dataset": dataset,
            "protocol_sha256": digest_json(protocol), "seed": seed,
            "status": self.status, "files": {},
            "upstreams": [{"artifact_id": run.manifest["artifact_id"],
                           "stage": run.manifest["stage"], "path": str(run.path)}
                          for run in upstreams or []],
            "repository_authority_validation": "not_run",
            "scientific_numerical_validation": "not_run",
            "claim_scope": "MC-only educational/technical demo",
            "context": context or {},
        }

    def __enter__(self):
        self.transaction.__enter__()
        try:
            self.manifest["software"] = software_record()
            optional = {}
            for name in ("pyhf", "scipy", "jsonschema", "jsonpatch"):
                try:
                    optional[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    optional[name] = None
            self.manifest["software"]["research_packages"] = optional
            self.write_json("protocol.json", self.protocol)
        except BaseException as error:
            self.transaction.__exit__(type(error), error, error.__traceback__)
            raise
        return self

    def write_json(self, name: str, value: Any) -> Path:
        name = _filename(name)
        if name == "manifest.json" or name in self.manifest["files"]:
            raise ResearchError("artifact filename already reserved")
        path = self.path / name
        path.write_bytes(canonical_json_bytes(value))
        self.register_file(name)
        return path

    def register_file(self, name: str) -> None:
        name = _filename(name)
        path = self.path / name
        if name == "manifest.json" or name in self.manifest["files"]:
            raise ResearchError("artifact filename already reserved")
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self.path.resolve():
            raise ResearchError("invalid artifact payload path")
        self.manifest["files"][name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}

    def register_streamed_file(self, name: str, *, sha256: str, size_bytes: int) -> None:
        """Register bytes hashed by the writer without rereading the payload."""
        name = _filename(name)
        path = self.path / name
        if name == "manifest.json" or name in self.manifest["files"]:
            raise ResearchError("artifact filename already reserved")
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self.path.resolve():
            raise ResearchError("invalid artifact payload path")
        if (not isinstance(sha256, str) or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
                or type(size_bytes) is not int or size_bytes < 0
                or path.stat().st_size != size_bytes):
            raise ResearchError("invalid streamed artifact receipt")
        self.manifest["files"][name] = {"sha256": sha256, "size_bytes": size_bytes}
        self._stream_verified_files.add(name)

    def __exit__(self, kind, error, traceback):
        terminal = isinstance(error, ResearchStateError)
        recorded_failure = error is not None
        if recorded_failure:
            self.status = error.status if isinstance(error, ResearchError) else 'internal_error'
            self.manifest["status"] = self.status
            self.manifest["reason"] = str(error)
            self.manifest["error_type"] = type(error).__name__
            self.manifest["exit_code"] = getattr(error, 'exit_code', 70)
        if error is None or recorded_failure:
            try:
                # Recheck each payload just before publication, including files
                # registered by stages that stream data directly to disk.
                bound = LoadedRun(self.path, self.manifest)
                for name in self.manifest["files"]:
                    if name not in self._stream_verified_files:
                        bound.file(name)
                self.manifest["artifact_id"] = digest_json(self.manifest)
                (self.path / "manifest.json").write_bytes(canonical_json_bytes(self.manifest))
            except BaseException as publish_error:
                self.transaction.__exit__(type(publish_error), publish_error, publish_error.__traceback__)
                raise
            # Ordinary errors keep the standard failure receipt as well as the
            # research manifest; scientific terminal states remain normal exits.
            self.transaction.__exit__(kind, error, traceback) if recorded_failure and not terminal else self.transaction.__exit__(None, None, None)
            return terminal
        return self.transaction.__exit__(kind, error, traceback)
