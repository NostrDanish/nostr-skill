---
name: nostr
description: Build, debug, and operate anything on the Nostr protocol. Use whenever the task involves Nostr clients, bots, relays, or keys — publishing/signing/verifying events, generating or converting keys (npub/nsec/note/nevent/naddr/nprofile), querying relays with NIP-01 filters, choosing the right NIP for a feature (DMs NIP-17, zaps NIP-57, groups NIP-29, long-form NIP-23, lists NIP-51, outbox model NIP-65, Blossom media), setting up a relay (strfry, khatru, nostr-rs-relay), NIP-07 browser signing, NIP-46 remote signers, NIP-98 HTTP auth, or decoding any bech32 nostr identifier. Triggers on "nostr", NIP numbers, relay URLs (wss://), and npub1/nsec1/note1/nevent1/naddr1 strings.
---

# Nostr

## Core model (memorize this, everything follows)

- An **event** is JSON: `{id, pubkey, created_at, kind, tags, content, sig}`. `id` = sha256 of `[0, pubkey, created_at, kind, tags, content]` serialized UTF-8 with no whitespace. `sig` = BIP340 Schnorr over the id.
- **Kinds**: 0 metadata, 1 short note, 3 contacts, 4 legacy DM (avoid), 6/16 reposts, 7 reaction, 9735 zap receipt, 10002 relay list, 30023 long-form. Full table: [references/kinds.md](references/kinds.md).
- Kind ranges (NIP-01): **regular** = kinds 1, 2, 4–44, and 1000–9999 (store every version). **Replaceable** = 0, 3, and 10000–19999 (newest per pubkey+kind). **Ephemeral** = 20000–29999 (not stored). **Addressable** = 30000–39999 (newest per pubkey+kind+`d`). Kind 0 and 3 are replaceable. Kind 2 and 41 are regular.
- **Wire protocol** (client→relay): `["EVENT", ev]`, `["REQ", sub_id, filter...]`, `["CLOSE", sub_id]`, `["AUTH", ev]`. Relay→client: `["EVENT", sub_id, ev]`, `["EOSE", sub_id]`, `["OK", id, bool, msg]`, `["NOTICE", msg]`, `["CLOSED", sub_id, msg]`, `["COUNT", ...]`, `["AUTH", challenge]`.
- Filters: `ids`, `authors`, `kinds`, `#<single-letter>` tag filters, `since`/`until`, `limit`. `search` is NIP-50 and relay-optional. `ids`, `authors`, `#e` and `#p` must be exact 64-character lowercase hex — prefixes are not valid NIP-01. Only single-letter tags are indexed; `#category` matches nothing on a stock relay.

## Task routing

| Task | Do this |
|---|---|
| Generate keys, convert npub/nsec/note, decode any bech32, sign/verify an event, NIP-44 encrypt/decrypt | Run `scripts/nostr_key.py`. Secret arg is `env` (reads `NOSTR_SECRET_KEY`); pass `-` to read event JSON from stdin. `selftest` checks the BIP-340 vector. |
| One-off relay query, publish a signed event, fetch NIP-11 relay doc | Run `scripts/nostr_query.py` (`pip install websockets`). It answers NIP-42 AUTH when `NOSTR_SECRET_KEY` is set and rejects events that fail verification. |
| The current text of a NIP, or which NIP defines a kind | Use the `nostr-nips` skill. This file is a map, not a substitute for the spec. |
| `nak` on the command line | Use the `nak` skill. With no key set, nak signs as the public default key `01`. |
| Blossom upload, download, delete | Use the `blossom` skill. Auth is kind 24242, base64url, not NIP-96. |
| An existing NIP-90 data-vending machine | Use the `nostr-dvm` skill. NIP-90 is marked unrecommended; don't start a new product on it. |
| Build a client/bot/app, pick libraries, signers, subscriptions, DMs, zaps | Read [references/client-dev.md](references/client-dev.md) |
| Decide which NIP to use, check if a NIP is deprecated | Read [references/nips.md](references/nips.md) |
| Look up an event kind number or tag convention | Read [references/kinds.md](references/kinds.md) |
| Install/configure/secure a relay | Read [references/relay-ops.md](references/relay-ops.md) |

## Non-negotiable rules

1. **The nsec IS the account.** Never log it, commit it, send it to any server/relay, or ask the user to paste it where it isn't needed. Web clients use NIP-07 (`window.nostr`) or NIP-46 remote signers; only bots/backends hold nsecs, in env vars.
2. **Never hand-roll crypto for production apps** — use the audited libraries in client-dev.md. `scripts/nostr_key.py` is stdlib-only for portability (tooling, key conversion, verifying, one-off signing). `selftest` covers the BIP-340 zero-aux vector, an event round-trip, and NIP-44 round-trips including empty plaintext. It is not constant-time and it is not the full BIP/NIP vector suite.
3. **NIP-04 is dead, NIP-96 is dead.** DMs = NIP-17 (NIP-44 encryption + NIP-59 gift wrap). Media = Blossom. Deprecated NIPs with their replacements: [references/nips.md](references/nips.md).
4. **Publish to the user's write relays, read from their read relays** (NIP-65 kind-10002 lists). Querying only one big relay is the #1 client bug. Fetch relay lists from a few indexer relays first.
5. **Verify before trusting**: check `id` matches the serialization and `sig` verifies, especially for kind 0/3/10002 and anything driving payments (zap receipts: verify the invoice actually paid — the event alone proves nothing).
6. **Replaceable ≠ deleted.** Updating kind 0/3 or an addressable event leaves the old version on some relays. NIP-09 deletion is a *request*; relays may honor it, mirrors won't.
7. `created_at` is client-supplied and untrusted. Use it for display ordering, never for security decisions.

## Quick sanity checks while coding

- Event id must be recomputed from fields, never trusted from input.
- `tags` is an array of arrays, not an object. A NIP-10 marked reply is `["e", "<id>", "<relay-or-empty>", "root"|"reply", "<author-pubkey>"]`: the marker is 4th, the author pubkey is 5th. A plain NIP-01 `e` tag uses the 4th element as the author pubkey, so the word `reply` does not belong there. Top-level replies carry only a `root` marker.
- bech32 (not bech32m) for all NIP-19 entities; npub/nsec/note are raw 32 bytes, nprofile/nevent/naddr are TLV.
- WebSocket relays speak text frames of JSON arrays; send one filter per REQ element, multiple filters in one REQ are OR'd.
- Subscription results are streaming: wait for `EOSE` before concluding a query is complete, and keep the sub open for live updates.
