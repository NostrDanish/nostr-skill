#!/usr/bin/env python3
"""nostr_key.py — zero-dependency Nostr key, encoding & signing toolkit.

Pure stdlib (hashlib, hmac, secrets, json). Implements:
  - secp256k1 BIP340 Schnorr sign/verify (NIP-01)
  - keypair generation, nsec/npub/note bech32 encode/decode (NIP-19)
  - nprofile/nevent/naddr TLV encode/decode (NIP-19)
  - event id computation and event signing (NIP-01)
  - NIP-44 v2 payload encrypt/decrypt (ChaCha20+HMAC, secp256k1 ECDH)

CLI:
  python3 nostr_key.py gen                              # new keypair (hex + nsec/npub)
  python3 nostr_key.py pub <nsec|hex-seckey>            # derive public key
  python3 nostr_key.py encode <hex> <npub|note|nsec>    # bech32 encode
  python3 nostr_key.py decode <bech32-string>           # decode any NIP-19 entity
  python3 nostr_key.py sign <nsec|hex-seckey> '<event-json-without-id-pubkey-sig>'
  python3 nostr_key.py verify '<full-event-json>'
  python3 nostr_key.py nip44-encrypt <nsec|hex-seckey> <recipient-npub|hex-pubkey> <plaintext>
  python3 nostr_key.py nip44-decrypt <nsec|hex-seckey> <sender-npub|hex-pubkey> <payload>
"""
import base64
import hashlib
import hmac as hmac_mod
import json
import secrets
import sys

# ---------------- secp256k1 field/curve ----------------
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)
INF = None


def _inv(x, m=P):
    return pow(x, m - 2, m)


def _add(p, q):
    if p is INF:
        return q
    if q is INF:
        return p
    if p[0] == q[0]:
        if (p[1] + q[1]) % P == 0:
            return INF
        lam = (3 * p[0] * p[0]) * _inv(2 * p[1]) % P
    else:
        lam = (q[1] - p[1]) * _inv(q[0] - p[0]) % P
    x = (lam * lam - p[0] - q[0]) % P
    return (x, (lam * (p[0] - x) - p[1]) % P)


def _mul(k, pt=G):
    r = INF
    while k:
        if k & 1:
            r = _add(r, pt)
        pt = _add(pt, pt)
        k >>= 1
    return r


def _lift_x(x):
    y = pow((x * x * x + 7) % P, (P + 1) // 4, P)
    if y & 1:
        y = P - y
    return (x, y)


def _i2b(i):
    return i.to_bytes(32, "big")


def _b2i(b):
    return int.from_bytes(b, "big")


def _tagged(tag, *msgs):
    th = hashlib.sha256(tag.encode()).digest()
    h = hashlib.sha256(th + th)
    for m in msgs:
        h.update(m)
    return h.digest()


# ---------------- BIP340 Schnorr ----------------
def schnorr_sign(msg32, seckey_bytes, aux=None):
    d0 = _b2i(seckey_bytes)
    if not 1 <= d0 < N:
        raise ValueError("invalid secret key")
    pub = _mul(d0)
    d = N - d0 if pub[1] & 1 else d0
    aux = aux if aux is not None else secrets.token_bytes(32)
    t = bytes(a ^ b for a, b in zip(_i2b(d), _tagged("BIP0340/aux", aux)))
    k0 = _b2i(_tagged("BIP0340/nonce", t, _i2b(pub[0]), msg32)) % N
    if k0 == 0:
        raise RuntimeError("nonce is zero (astronomically unlikely)")
    R = _mul(k0)
    k = N - k0 if R[1] & 1 else k0
    e = _b2i(_tagged("BIP0340/challenge", _i2b(R[0]), _i2b(pub[0]), msg32)) % N
    return _i2b(R[0]) + _i2b((k + e * d) % N)


def schnorr_verify(msg32, pubkey32, sig64):
    if len(sig64) != 64 or len(pubkey32) != 32:
        return False
    px = _b2i(pubkey32)
    if px >= P:
        return False
    r, s = _b2i(sig64[:32]), _b2i(sig64[32:])
    if r >= P or s >= N:
        return False
    e = _b2i(_tagged("BIP0340/challenge", sig64[:32], pubkey32, msg32)) % N
    R = _add(_mul(s), _mul(N - e, _lift_x(px)))
    return R is not INF and not (R[1] & 1) and R[0] == r


# ---------------- bech32 (BIP-173, NIP-19 uses bech32 not bech32m) ----------------
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _polymod(vals):
    chk = 1
    for v in vals:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i, g in enumerate([0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]):
            if (top >> i) & 1:
                chk ^= g
    return chk


def _convertbits(data, frombits, tobits, pad=True):
    acc, bits, out = 0, 0, []
    mx = (1 << tobits) - 1
    for v in data:
        acc = (acc << frombits) | v
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & mx)
    if pad and bits:
        out.append((acc << (tobits - bits)) & mx)
    elif bits >= frombits or ((acc << (tobits - bits)) & mx):
        raise ValueError("invalid padding")
    return out


def bech32_encode(hrp, data_bytes):
    data = _convertbits(data_bytes, 8, 5)
    pm = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ 1
    return hrp + "1" + "".join(_CHARSET[d] for d in data + [(pm >> 5 * (5 - i)) & 31 for i in range(6)])


def bech32_decode(s):
    if any(ord(c) < 33 or ord(c) > 126 for c in s):
        raise ValueError("invalid character")
    if s.lower() != s and s.upper() != s:
        raise ValueError("mixed case")
    s = s.lower()
    pos = s.rfind("1")
    if pos < 1 or pos + 7 > len(s):
        raise ValueError("bad separator")
    hrp = s[:pos]
    data = [_CHARSET.index(c) for c in s[pos + 1:]]
    if _polymod(_hrp_expand(hrp) + data) != 1:
        raise ValueError("bad checksum")
    return hrp, bytes(_convertbits(data[:-6], 5, 8, False))


# ---------------- NIP-19 entities ----------------
def npub_encode(pubkey_hex):
    return bech32_encode("npub", bytes.fromhex(pubkey_hex))


def nsec_encode(seckey_hex):
    return bech32_encode("nsec", bytes.fromhex(seckey_hex))


def note_encode(event_id_hex):
    return bech32_encode("note", bytes.fromhex(event_id_hex))


def _tlv_encode(entries):
    out = b""
    for t, v in entries:
        out += bytes([t, len(v)]) + v
    return out


def _tlv_decode(raw):
    entries = []
    i = 0
    while i < len(raw):
        t, ln = raw[i], raw[i + 1]
        entries.append((t, raw[i + 2:i + 2 + ln]))
        i += 2 + ln
    return entries


def nprofile_encode(pubkey_hex, relays=None):
    entries = [(0, bytes.fromhex(pubkey_hex))]
    entries += [(1, r.encode()) for r in (relays or [])]
    return bech32_encode("nprofile", _tlv_encode(entries))


def nevent_encode(event_id_hex, relays=None, author_hex=None, kind=None):
    entries = [(0, bytes.fromhex(event_id_hex))]
    entries += [(1, r.encode()) for r in (relays or [])]
    if author_hex:
        entries.append((2, bytes.fromhex(author_hex)))
    if kind is not None:
        entries.append((3, kind.to_bytes(4, "big")))
    return bech32_encode("nevent", _tlv_encode(entries))


def naddr_encode(identifier, pubkey_hex, kind, relays=None):
    entries = [(0, identifier.encode())]
    entries += [(1, r.encode()) for r in (relays or [])]
    entries.append((2, bytes.fromhex(pubkey_hex)))
    entries.append((3, kind.to_bytes(4, "big")))
    return bech32_encode("naddr", _tlv_encode(entries))


def decode_entity(s):
    """Decode any NIP-19 bech32 string into a dict."""
    hrp, raw = bech32_decode(s)
    if hrp in ("npub", "nsec", "note"):
        if len(raw) != 32:
            raise ValueError("expected 32 bytes")
        return {"type": hrp, "hex": raw.hex()}
    if hrp in ("nprofile", "nevent", "naddr"):
        out = {"type": hrp, "relays": []}
        for t, v in _tlv_decode(raw):
            if t == 0:
                key = {"nprofile": "pubkey", "nevent": "event_id", "naddr": "identifier"}[hrp]
                out[key] = v.hex() if hrp != "naddr" else v.decode()
            elif t == 1:
                out["relays"].append(v.decode())
            elif t == 2:
                out["author"] = v.hex()
            elif t == 3:
                out["kind"] = int.from_bytes(v, "big")
        return out
    raise ValueError(f"unknown prefix: {hrp}")


# ---------------- NIP-01 events ----------------
def event_id(ev):
    serialized = json.dumps(
        [0, ev["pubkey"], ev["created_at"], ev["kind"], ev["tags"], ev["content"]],
        separators=(",", ":"), ensure_ascii=False,
    ).encode()
    return hashlib.sha256(serialized).hexdigest()


def sign_event(ev, seckey_hex):
    """Fill pubkey, id, sig. `ev` needs kind, created_at, tags, content."""
    ev = dict(ev)
    ev["pubkey"] = _i2b(_mul(_b2i(bytes.fromhex(seckey_hex)))[0]).hex() if isinstance(seckey_hex, str) else None
    ev["id"] = event_id(ev)
    ev["sig"] = schnorr_sign(bytes.fromhex(ev["id"]), bytes.fromhex(seckey_hex)).hex()
    return ev


def verify_event(ev):
    if event_id(ev) != ev.get("id"):
        return False
    return schnorr_verify(bytes.fromhex(ev["id"]), bytes.fromhex(ev["pubkey"]), bytes.fromhex(ev["sig"]))


# ---------------- NIP-44 v2 encryption ----------------
def _chacha20_block(key, counter, nonce):
    def rotl(v, n):
        return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF

    def qr(st, a, b, c, d):
        st[a] = (st[a] + st[b]) & 0xFFFFFFFF; st[d] = rotl(st[d] ^ st[a], 16)
        st[c] = (st[c] + st[d]) & 0xFFFFFFFF; st[b] = rotl(st[b] ^ st[c], 12)
        st[a] = (st[a] + st[b]) & 0xFFFFFFFF; st[d] = rotl(st[d] ^ st[a], 8)
        st[c] = (st[c] + st[d]) & 0xFFFFFFFF; st[b] = rotl(st[b] ^ st[c], 7)

    const = b"expand 32-byte k"
    st = [int.from_bytes(const[i:i + 4], "little") for i in range(0, 16, 4)]
    st += [int.from_bytes(key[i:i + 4], "little") for i in range(0, 32, 4)]
    st += [counter] + [int.from_bytes(nonce[i:i + 4], "little") for i in range(0, 12, 4)]
    w = st[:]
    for _ in range(10):
        qr(w, 0, 4, 8, 12); qr(w, 1, 5, 9, 13); qr(w, 2, 6, 10, 14); qr(w, 3, 7, 11, 15)
        qr(w, 0, 5, 10, 15); qr(w, 1, 6, 11, 12); qr(w, 2, 7, 8, 13); qr(w, 3, 4, 9, 14)
    return b"".join(((w[i] + st[i]) & 0xFFFFFFFF).to_bytes(4, "little") for i in range(16))


def _chacha20_xor(key, nonce, data):
    out = b""
    for i in range(0, len(data), 64):
        out += bytes(a ^ b for a, b in zip(data[i:i + 64], _chacha20_block(key, i // 64, nonce)))
    return out


def _hkdf_extract(salt, ikm):
    return hmac_mod.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk, info, length):
    out, t = b"", b""
    for i in range(1, (length + 31) // 32 + 1):
        t = hmac_mod.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
    return out[:length]


def nip44_conversation_key(seckey_hex, pubkey_hex):
    shared = _mul(_b2i(bytes.fromhex(seckey_hex)), _lift_x(_b2i(bytes.fromhex(pubkey_hex))))
    return _hkdf_extract(b"nip44-v2", _i2b(shared[0]))


def _pad(msg):
    ln = len(msg)
    if ln < 0 or ln > 65535:
        raise ValueError("message length must be 0..65535")
    if ln <= 32:
        np = 32
    else:
        next_power = 1 << (ln - 1).bit_length()
        chunk = 32 if next_power <= 256 else next_power // 8
        np = chunk * ((ln - 1) // chunk + 1)
    return ln.to_bytes(2, "big") + msg + b"\x00" * (np - ln)


def _unpad(data):
    ln = int.from_bytes(data[:2], "big")
    if ln < 1 or ln > len(data) - 2 or any(data[2 + ln:]):
        raise ValueError("invalid padding")
    return data[2:2 + ln]


def nip44_encrypt(seckey_hex, pubkey_hex, plaintext):
    ck = nip44_conversation_key(seckey_hex, pubkey_hex)
    nonce = secrets.token_bytes(32)
    keys = _hkdf_expand(ck, nonce, 76)
    enc_key, enc_nonce, mac_key = keys[:32], keys[32:44], keys[44:]
    padded = _pad(plaintext.encode())
    ct = _chacha20_xor(enc_key, enc_nonce, padded)
    mac = hmac_mod.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return base64.b64encode(b"\x02" + nonce + ct + mac).decode()


def nip44_decrypt(seckey_hex, pubkey_hex, payload):
    raw = base64.b64decode(payload)
    if raw[0] != 2:
        raise ValueError("unsupported NIP-44 version")
    nonce, ct, mac = raw[1:33], raw[33:-32], raw[-32:]
    ck = nip44_conversation_key(seckey_hex, pubkey_hex)
    keys = _hkdf_expand(ck, nonce, 76)
    enc_key, enc_nonce, mac_key = keys[:32], keys[32:44], keys[44:]
    if not hmac_mod.compare_digest(mac, hmac_mod.new(mac_key, nonce + ct, hashlib.sha256).digest()):
        raise ValueError("MAC mismatch — wrong keys or corrupted payload")
    return _unpad(_chacha20_xor(enc_key, enc_nonce, ct)).decode()


# ---------------- helpers / CLI ----------------
def generate_keypair():
    while True:
        sk = secrets.token_bytes(32)
        if 1 <= _b2i(sk) < N:
            return sk.hex(), _i2b(_mul(_b2i(sk))[0]).hex()


def _resolve_seckey(s):
    if s.startswith("nsec1"):
        return decode_entity(s)["hex"]
    if len(s) == 64:
        return s.lower()
    raise ValueError("expected nsec1... or 64-char hex secret key")


def _resolve_pubkey(s):
    if s.startswith("npub1") or s.startswith("nprofile1"):
        d = decode_entity(s)
        return d["hex"] if "hex" in d else d["pubkey"]
    if len(s) == 64:
        return s.lower()
    raise ValueError("expected npub1... or 64-char hex public key")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "gen":
        sk, pk = generate_keypair()
        print(json.dumps({
            "secret_key_hex": sk, "nsec": nsec_encode(sk),
            "public_key_hex": pk, "npub": npub_encode(pk),
        }, indent=2))
        print("\n⚠️  The nsec IS the account. Never commit it, never send it to a relay or server.", file=sys.stderr)
    elif cmd == "pub":
        sk = _resolve_seckey(sys.argv[2])
        pk = _i2b(_mul(_b2i(bytes.fromhex(sk)))[0]).hex()
        print(json.dumps({"public_key_hex": pk, "npub": npub_encode(pk)}, indent=2))
    elif cmd == "encode":
        print(bech32_encode(sys.argv[3], bytes.fromhex(sys.argv[2])))
    elif cmd == "decode":
        print(json.dumps(decode_entity(sys.argv[2]), indent=2))
    elif cmd == "sign":
        ev = sign_event(json.loads(sys.argv[3]), _resolve_seckey(sys.argv[2]))
        print(json.dumps(ev, ensure_ascii=False))
    elif cmd == "verify":
        ok = verify_event(json.loads(sys.argv[2]))
        print("VALID" if ok else "INVALID")
        sys.exit(0 if ok else 1)
    elif cmd == "nip44-encrypt":
        print(nip44_encrypt(_resolve_seckey(sys.argv[2]), _resolve_pubkey(sys.argv[3]), sys.argv[4]))
    elif cmd == "nip44-decrypt":
        print(nip44_decrypt(_resolve_seckey(sys.argv[2]), _resolve_pubkey(sys.argv[3]), sys.argv[4]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
