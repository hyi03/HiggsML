from __future__ import annotations

import hashlib


def event_split(event_number: int, channel_number: int = 0) -> str:
    payload = f"{int(channel_number)}:{int(event_number)}".encode()
    bucket = int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "validation"
    return "test"

