from __future__ import annotations

import hashlib


def event_split(event_number: int, channel_number: int) -> str:
    payload = f"{int(channel_number)}:{int(event_number)}".encode("utf-8")
    bucket = int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % 10
    return "train" if bucket < 6 else "validation" if bucket < 8 else "test"
