from dataclasses import replace
from hashlib import sha256

import pytest

from higgsml.errors import ResearchError
from higgsml._manifest import canonical_json_bytes
from higgsml.inference.seed_blocks import (
    canonical_seed_blocks, pairing_contract, stream_identity, validate_seed_blocks,
)


def test_canonical_registry_is_exact_5_by_16_and_digest_bound():
    blocks = canonical_seed_blocks()
    assert len(blocks) == 5
    assert all(len(block.candidate_keys) == 16 for block in blocks)
    assert len({key for block in blocks for key in block.candidate_keys}) == 80
    validate_seed_blocks(blocks)
    with pytest.raises(ResearchError):
        validate_seed_blocks(blocks[:-1])
    with pytest.raises(ResearchError):
        validate_seed_blocks((replace(blocks[0], candidate_keys=blocks[1].candidate_keys), *blocks[1:]))
    with pytest.raises(ResearchError):
        canonical_seed_blocks({**pairing_contract(), "block_size": 15})
    altered = {**pairing_contract(), "block_size": 15}
    altered["contract_digest"] = sha256(canonical_json_bytes(
        {key: value for key, value in altered.items() if key != "contract_digest"})).hexdigest()
    with pytest.raises(ResearchError, match="semantics"):
        canonical_seed_blocks(altered)


def test_stream_identity_is_stable_order_independent_and_seed_isolated():
    digest = pairing_contract()["contract_digest"]
    args = dict(contract_digest=digest, stage="assessment", mu=1, training_seed=42,
                outer_index=None, stream_kind="physical_observation", replica_index=7,
                toy_base_seed=42001)
    assert stream_identity(**args) == stream_identity(**dict(reversed(list(args.items()))))
    assert stream_identity(**args)["stream_id"] != stream_identity(**{**args, "training_seed": 43})["stream_id"]
    assert stream_identity(**args)["algorithm"] == "sha256-first-64-big-endian"
