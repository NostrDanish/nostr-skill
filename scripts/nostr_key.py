#!/usr/bin/env python3
"""Public NIP-19 identifier codec.

This tool intentionally does NOT generate, decode, print, sign with, or encrypt
private keys. In particular, nsec is rejected. Use a trusted wallet, NIP-07,
NIP-46 remote signer, or reviewed signer service for all secret-key operations.
"""
from __future__ import annotations
import argparse
import json
import re
from typing import Iterable

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)

def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]

def _polymod(values: Iterable[int]) -> int:
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for bit, generator in enumerate(GENERATOR):
            if (top >> bit) & 1:
                chk ^= generator
    return chk

def _convertbits(data: Iterable[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = bits = 0
    result: list[int] = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError("invalid data value")
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            result.append((acc >> bits) & maxv)
    if pad:
        if bits:
            result.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid bit conversion padding")
    return result

def bech32_encode(hrp: str, payload: bytes) -> str:
    data = _convertbits(payload, 8, 5, True)
    checksum = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ 1
    check = [(checksum >> (5 * (5 - i))) & 31 for i in range(6)]
    return hrp + "1" + "".join(CHARSET[x] for x in data + check)

def bech32_decode(value: str) -> tuple[str, bytes]:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("invalid bech32 input length")
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("invalid bech32 character")
    if value.lower() != value and value.upper() != value:
        raise ValueError("mixed-case bech32 is invalid")
    value = value.lower()
    pos = value.rfind("1")
    if pos < 1 or pos + 7 > len(value):
        raise ValueError("invalid bech32 separator or checksum length")
    hrp = value[:pos]
    try:
        data = [CHARSET.index(c) for c in value[pos + 1:]]
    except ValueError as exc:
        raise ValueError("invalid bech32 alphabet") from exc
    if _polymod(_hrp_expand(hrp) + data) != 1:
        raise ValueError("invalid bech32 checksum")
    return hrp, bytes(_convertbits(data[:-6], 5, 8, False))

def _hex32(value: str, label: str) -> bytes:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError(f"{label} must be exactly 64 hexadecimal characters")
    return bytes.fromhex(value)

def _tlv_encode(entries: list[tuple[int, bytes]]) -> bytes:
    out = bytearray()
    for typ, value in entries:
        if not 0 <= typ <= 255 or len(value) > 255:
            raise ValueError("NIP-19 TLV entry exceeds one-byte type/length")
        out.extend((typ, len(value)))
        out.extend(value)
    return bytes(out)

def _tlv_decode(raw: bytes) -> list[tuple[int, bytes]]:
    entries = []
    offset = 0
    while offset < len(raw):
        if offset + 2 > len(raw):
            raise ValueError("truncated TLV header")
        typ, length = raw[offset], raw[offset + 1]
        offset += 2
        if offset + length > len(raw):
            raise ValueError("truncated TLV value")
        entries.append((typ, raw[offset:offset + length]))
        offset += length
    return entries

def decode_entity(value: str) -> dict:
    hrp, raw = bech32_decode(value)
    if hrp == "nsec":
        raise ValueError("nsec decoding is intentionally disabled; never expose private keys to an agent")
    if hrp in ("npub", "note"):
        if len(raw) != 32:
            raise ValueError(f"{hrp} payload must be 32 bytes")
        return {"type": hrp, "hex": raw.hex()}
    if hrp not in ("nprofile", "nevent", "naddr"):
        raise ValueError(f"unsupported NIP-19 entity type: {hrp}")
    result = {"type": hrp, "relays": [], "unknown_tlv": []}
    seen: set[int] = set()
    for typ, value_bytes in _tlv_decode(raw):
        if typ in (0, 2, 3) and typ in seen:
            raise ValueError(f"duplicate singleton TLV field: {typ}")
        if typ in (0, 2, 3):
            seen.add(typ)
        if typ == 0:
            field = {"nprofile": "pubkey", "nevent": "event_id", "naddr": "identifier"}[hrp]
            if hrp == "naddr":
                result[field] = value_bytes.decode("utf-8")
            else:
                if len(value_bytes) != 32:
                    raise ValueError(f"{field} TLV must be 32 bytes")
                result[field] = value_bytes.hex()
        elif typ == 1:
            result["relays"].append(value_bytes.decode("utf-8"))
        elif typ == 2 and hrp in ("nevent", "naddr"):
            if len(value_bytes) != 32:
                raise ValueError("author/pubkey TLV must be 32 bytes")
            result["author" if hrp == "nevent" else "pubkey"] = value_bytes.hex()
        elif typ == 3 and hrp in ("nevent", "naddr"):
            if len(value_bytes) != 4:
                raise ValueError("kind TLV must be 4 bytes")
            result["kind"] = int.from_bytes(value_bytes, "big")
        else:
            result["unknown_tlv"].append({"type": typ, "hex": value_bytes.hex()})
    required = {"nprofile": ("pubkey",), "nevent": ("event_id",), "naddr": ("identifier", "pubkey", "kind")}[hrp]
    if any(field not in result for field in required):
        raise ValueError(f"missing required {hrp} TLV field")
    return result

def encode_entity(entity_type: str, value: str, relays: list[str] | None = None,
                  author: str | None = None, kind: int | None = None) -> str:
    if entity_type == "npub":
        return bech32_encode("npub", _hex32(value, "public key"))
    if entity_type == "note":
        return bech32_encode("note", _hex32(value, "event id"))
    if entity_type not in ("nprofile", "nevent", "naddr"):
        raise ValueError("only public NIP-19 entities can be encoded; nsec is prohibited")
    relays = relays or []
    entries: list[tuple[int, bytes]] = []
    if entity_type == "nprofile":
        entries.append((0, _hex32(value, "public key")))
    elif entity_type == "nevent":
        entries.append((0, _hex32(value, "event id")))
    else:
        identifier = value.encode("utf-8")
        if not identifier:
            raise ValueError("naddr identifier must not be empty")
        entries.append((0, identifier))
    for relay in relays:
        entries.append((1, relay.encode("utf-8")))
    if author:
        entries.append((2, _hex32(author, "author public key")))
    if entity_type == "naddr" and not author:
        raise ValueError("naddr requires --author")
    if kind is not None or entity_type == "naddr":
        if kind is None or not 0 <= kind <= 0xFFFFFFFF:
            raise ValueError("kind must be an integer in the uint32 range")
        entries.append((3, kind.to_bytes(4, "big")))
    return bech32_encode(entity_type, _tlv_encode(entries))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    decode = sub.add_parser("decode", help="decode a public NIP-19 entity (nsec rejected)")
    decode.add_argument("entity")
    encode = sub.add_parser("encode", help="encode npub or note from public hex")
    encode.add_argument("entity_type", choices=("npub", "note"))
    encode.add_argument("hex_value")
    for entity_type in ("nprofile", "nevent", "naddr"):
        item = sub.add_parser(entity_type, help=f"encode a {entity_type} public reference")
        item.add_argument("value", help="public key/event id or naddr identifier")
        item.add_argument("--relay", action="append", default=[])
        if entity_type in ("nevent", "naddr"):
            item.add_argument("--author", help="author public key hex")
            item.add_argument("--kind", type=int)
        else:
            item.set_defaults(author=None, kind=None)
    args = parser.parse_args()
    try:
        if args.command == "decode":
            print(json.dumps(decode_entity(args.entity), ensure_ascii=False))
        elif args.command == "encode":
            print(encode_entity(args.entity_type, args.hex_value))
        else:
            print(encode_entity(args.command, args.value, args.relay, args.author, args.kind))
        return 0
    except (ValueError, UnicodeDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())
