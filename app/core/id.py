"""
TypeID implementation reproducing id/id.go.
Produces URL-safe, globally unique, K-sortable UUIDv7-based TypeIDs: 'prefix_suffix'.
"""
from __future__ import annotations
import os
import time
from typing import Optional


# Crockford-style Base32 alphabet used by TypeID spec (excludes i, l, o, u)
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
ALPHABET_MAP = {c: i for i, c in enumerate(ALPHABET)}

PREFIX_PLAN = "plan"
PREFIX_FEATURE = "feat"
PREFIX_PRICE = "price"
PREFIX_SUBSCRIPTION = "sub"
PREFIX_USAGE_EVENT = "uevt"
PREFIX_ENTITLEMENT = "ent"
PREFIX_INVOICE = "inv"
PREFIX_LINE_ITEM = "li"
PREFIX_COUPON = "cpn"
PREFIX_PAYMENT = "pay"
PREFIX_COUPON_APP = "cpna"


def _generate_uuidv7_bytes() -> bytes:
    # 48-bit timestamp ms
    ms = int(time.time() * 1000)
    ts_bytes = ms.to_bytes(6, byteorder="big")
    rand_bytes = os.urandom(10)

    # version 7 in byte 6
    b6 = (rand_bytes[0] & 0x0F) | 0x70
    # variant (RFC 4122) in byte 8
    b8 = (rand_bytes[2] & 0x3F) | 0x80

    return (
        ts_bytes +
        bytes([b6, rand_bytes[1], b8]) +
        rand_bytes[3:10]
    )


def _encode_base32(data: bytes) -> str:
    # 16 bytes (128 bits) -> 26 base32 characters (130 bits, top 2 bits zero)
    val = int.from_bytes(data, byteorder="big")
    chars = []
    for _ in range(26):
        chars.append(ALPHABET[val & 0x1F])
        val >>= 5
    return "".join(reversed(chars))


class TypeID(str):
    @classmethod
    def new(cls, prefix: str) -> TypeID:
        raw = _generate_uuidv7_bytes()
        suffix = _encode_base32(raw)
        return cls(f"{prefix}_{suffix}")

    @property
    def prefix(self) -> str:
        parts = self.split("_", 1)
        return parts[0] if len(parts) == 2 else ""

    @property
    def suffix(self) -> str:
        parts = self.split("_", 1)
        return parts[1] if len(parts) == 2 else ""

    @classmethod
    def parse(cls, s: str, expected_prefix: Optional[str] = None) -> TypeID:
        if not s:
            raise ValueError("TypeID: empty string")
        if "_" not in s:
            raise ValueError(f"TypeID: missing underscore separator in {s!r}")
        parts = s.split("_", 1)
        prefix, suffix = parts[0], parts[1]
        if not prefix.isalnum() or not prefix.islower():
            raise ValueError(f"TypeID: invalid prefix {prefix!r}")
        if len(suffix) != 26:
            raise ValueError(f"TypeID: invalid suffix length {len(suffix)} for {s!r}")
        for c in suffix:
            if c not in ALPHABET_MAP:
                raise ValueError(f"TypeID: invalid character {c!r} in suffix of {s!r}")
        if expected_prefix and prefix != expected_prefix:
            raise ValueError(f"TypeID: expected prefix {expected_prefix!r}, got {prefix!r}")
        return cls(s)


def new_id(prefix: str) -> str:
    return str(TypeID.new(prefix))


def parse_id(s: str, expected_prefix: Optional[str] = None) -> str:
    return str(TypeID.parse(s, expected_prefix))
