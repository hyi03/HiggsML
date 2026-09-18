from higgsml.inference.marginal_coupling import canonical_seed_blocks, pairing_contract
from higgsml.inference.seed_blocks import stream_identity


def test_canonical_registry_is_exact_5_by_16_and_digest_bound():
    blocks = canonical_seed_blocks()
    assert len(blocks) == 5
    assert all(len(block.candidate_keys) == 16 for block in blocks)
    assert len({key for block in blocks for key in block.candidate_keys}) == 80
    assert all(block.pairing_contract_digest == pairing_contract()["contract_digest"] for block in blocks)


def test_stream_identity_is_stable_order_independent_and_seed_isolated():
    digest = pairing_contract()["contract_digest"]
    args = dict(contract_digest=digest, stage="assessment", mu=1, training_seed=42,
                outer_index=None, stream_kind="physical_observation", replica_index=7,
                toy_base_seed=42001)
    assert stream_identity(**args) == stream_identity(**dict(reversed(list(args.items()))))
    assert stream_identity(**args)["stream_id"] != stream_identity(**{**args, "training_seed": 43})["stream_id"]
    assert stream_identity(**args)["algorithm"] == "sha256-first-64-big-endian"
