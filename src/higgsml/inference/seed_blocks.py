"""Canonical within-seed blocks and reproducible random-stream identities."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from higgsml._manifest import canonical_json_bytes
from higgsml.errors import ResearchError
from higgsml.inference.attribution import SEEDS, SUBSETS, candidate_key, candidate_keys

PAIRING_CONTRACT_ID = "h4l-mass-off-within-seed-joint-v1"
STREAM_ALGORITHM = "sha256-first-64-big-endian"
STREAM_VERSION = "h4l-stream-v1"


def _digest(value) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True)
class SeedBlockSpec:
    seed: int
    candidate_keys: tuple[str, ...]
    block_id: str
    pairing_contract_digest: str
    analysis_contract_digest: str | None = None

    @property
    def rng_contract_digest(self):
        if self.analysis_contract_digest is None:
            return self.pairing_contract_digest
        return _digest({'pairing_contract_digest':self.pairing_contract_digest,
                        'analysis_contract_digest':self.analysis_contract_digest})

    def as_dict(self) -> dict:
        return {"seed": self.seed, "candidate_keys": list(self.candidate_keys),
                "block_id": self.block_id,
                "pairing_contract_digest": self.pairing_contract_digest}


def pairing_contract() -> dict:
    body = {"contract_id": PAIRING_CONTRACT_ID, "pairing_scope": "within_seed",
            "cross_seed_pairing": "none", "seeds": list(SEEDS),
            "subsets": list(SUBSETS), "candidate_family_size": 80,
            "block_size": 16}
    return {**body, "contract_digest": _digest(body)}


def _validate_contract(contract: dict) -> str:
    canonical = pairing_contract()
    if contract != canonical:
        raise ResearchError("pairing contract semantics or digest mismatch")
    return canonical["contract_digest"]


def canonical_seed_blocks(contract: dict | None = None) -> tuple[SeedBlockSpec, ...]:
    contract = pairing_contract() if contract is None else contract
    digest = _validate_contract(contract)
    blocks = []
    for seed in SEEDS:
        keys = tuple(candidate_key(seed, subset) for subset in SUBSETS)
        identity = {"pairing_contract_digest": digest, "seed": seed,
                    "candidate_keys": list(keys)}
        blocks.append(SeedBlockSpec(seed, keys, "seed-block:" + _digest(identity), digest))
    validate_seed_blocks(blocks, contract)
    return tuple(blocks)


def validate_seed_blocks(blocks, contract: dict | None = None) -> None:
    contract = pairing_contract() if contract is None else contract
    digest = _validate_contract(contract)
    blocks = tuple(blocks)
    if len(blocks) != len(SEEDS) or {b.seed for b in blocks} != set(SEEDS):
        raise ResearchError("seed blocks must cover seeds 42--46 exactly")
    seen = []
    for block in blocks:
        expected = tuple(candidate_key(block.seed, subset) for subset in SUBSETS)
        identity = {"pairing_contract_digest": digest, "seed": block.seed,
                    "candidate_keys": list(block.candidate_keys)}
        if (block.candidate_keys != expected or block.pairing_contract_digest != digest
                or block.block_id != "seed-block:" + _digest(identity)):
            raise ResearchError("invalid seed block identity or coalition coverage")
        seen.extend(block.candidate_keys)
    if len(seen) != len(set(seen)) or set(seen) != set(candidate_keys()):
        raise ResearchError("seed blocks must cover all 80 candidates without duplicates")


def stream_identity(*, contract_digest: str, stage: str, mu: int | float,
                    training_seed: int, outer_index: int | None, stream_kind: str,
                    candidate_if_auxiliary: str | None = None,
                    replica_index: int | None = None, toy_base_seed: int | None = None) -> dict:
    if training_seed not in SEEDS or not contract_digest or not stage or not stream_kind:
        raise ResearchError("invalid stream identity")
    if candidate_if_auxiliary is not None and candidate_if_auxiliary not in candidate_keys():
        raise ResearchError("unregistered auxiliary candidate")
    fields = {"version": STREAM_VERSION, "contract_digest": contract_digest,
              "stage": stage, "mu": mu, "training_seed": training_seed,
              "outer_index": outer_index, "stream_kind": stream_kind,
              "candidate_if_auxiliary": candidate_if_auxiliary,
              "replica_index": replica_index, "toy_base_seed": toy_base_seed}
    stream_id = _digest(fields)
    return {**fields, "algorithm": STREAM_ALGORITHM, "stream_id": stream_id,
            "seed": int.from_bytes(bytes.fromhex(stream_id[:16]), "big")}


def derive_seed(**identity) -> int:
    """Return the NumPy-compatible stable seed for a registered stream identity."""
    return stream_identity(**identity)["seed"]
