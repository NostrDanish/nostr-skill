---
name: nostr
description: Build, debug, and operate anything on the Nostr protocol. Use whenever the task involves Nostr clients, bots, relays, or keys — publishing/signing/verifying events, generating or converting keys (npub/nsec/note/nevent/naddr/nprofile), querying relays with NIP-01 filters, choosing the right NIP for a feature (DMs NIP-17, zaps NIP-57, groups NIP-29, long-form NIP-23, lists NIP-51, outbox model NIP-65, Blossom media), setting up a relay (strfry, khatru, nostr-rs-relay), NIP-07 browser signing, NIP-46 remote signers, NIP-98 HTTP auth, or decoding any bech32 nostr identifier. Triggers on "nostr", NIP numbers, relay URLs (wss://), and npub1/nsec1/note1/nevent1/naddr1 strings.
---

# Nostr

## Core model (memorize this, everything follows)

- An **event** is JSON: `{id, pubkey, created_at, kind, tags, content, sig}`. `id` = sha256 of `[0, pubkey, created_at, kind, tags, content]` serialized UTF-8 with no whitespace. `sig` = BIP340 Schnorr over the id.
- **Kinds**: 0 metadata, 1 short note, 3 contacts, 4 legacy DM (avoid), 6/16 reposts, 7 reaction, 9735 zap receipt, 10002 relay list, 30023 long-form. Full table: [references/kinds.md](references/kinds.md).
- Kind ranges define lifecycle: regular (stored forever), **replaceable** (10000–19999: newest per pubkey+kind wins), **ephemeral** (20000–29999: not stored), **addressable/parameterized replaceable** (30000–39999: newest per pubkey+kind+`d`-tag wins).
- **Wire protocol** (client→relay): `["EVENT", ev]`, `["REQ", sub_id, filter...]`, `["CLOSE", sub_id]`, `["AUTH", ev]`. Relay→client: `["EVENT", sub_id, ev]`, `["EOSE", sub_id]`, `["OK", id, bool, msg]`, `["NOTICE", msg]`, `["CLOSED", sub_id, msg]`, `["COUNT", ...]`, `["AUTH", challenge]`.
- Filters: `ids`, `authors`, `kinds`, `#<letter>` tag filters, `since`/`until`, `limit`, `search` (NIP-50). `ids`/`authors` accept hex prefixes.

## Task routing

| Task | Do this |
|---|---|
| Generate keys, convert npub/nsec/note, decode any bech32, sign/verify an event, NIP-44 encrypt/decrypt | Run `scripts/nostr_key.py` (zero dependencies). `selftest` checks BIP340 and NIP-44 vectors. Pass `-` and set `NOSTR_SECRET_KEY` instead of putting an nsec on the command line |
| One-off relay query, publish a signed event, fetch NIP-11 relay doc | Run `scripts/nostr_query.py` (needs `pip install websockets`) |
| Shell one-liners (fetch, encode, relay sync, blossom, git) | Use the `nak` skill. This skill's scripts are the fallback when nak is not installed |
| Read the current text of a NIP, or map a kind number to the NIP that defines it | Use the `nostr-nips` skill and fetch the raw file. Do not treat `references/nips.md` as the spec |
| Build a client/bot/app, pick libraries, signers, subscriptions, DMs, zaps | Read [references/client-dev.md](references/client-dev.md) |
| Upload, list, mirror, or authorize Blossom blobs | Use the `blossom` skill. NIP-96 is not the path |
| Pay or receive via Nostr Wallet Connect | Use the `nwc` skill. The connection URI is a secret |
| Decide which NIP to use, check if a NIP is deprecated | Read [references/nips.md](references/nips.md), then confirm status in the live NIPs README |
| Look up an event kind number or tag convention | Read [references/kinds.md](references/kinds.md) |
| Install/configure/secure a relay | Read [references/relay-ops.md](references/relay-ops.md) |
| Build or validate a SIP-01 kind 39697 web-index event | Use the `sip-01` skill |

## Non-negotiable rules

1. **The nsec IS the account.** Never log it, commit it, send it to any server/relay, or ask the user to paste it where it isn't needed. Web clients use NIP-07 (`window.nostr`) or NIP-46 remote signers; only bots/backends hold nsecs, in env vars.
2. **Never hand-roll crypto for production apps** — use the audited libraries in client-dev.md. `scripts/nostr_key.py` is stdlib-only for portability (tooling, key conversion, verifying, one-off signing). `python3 scripts/nostr_key.py selftest` checks the BIP340 and NIP-44 vectors shipped in the script. It is not constant-time. Put the secret in `NOSTR_SECRET_KEY` and pass `-`; an nsec argument is visible in the process list.
3. **NIP-04 is dead, NIP-96 is dead.** DMs = NIP-17 (NIP-44 encryption + NIP-59 gift wrap). Media = Blossom. Deprecated NIPs with their replacements: [references/nips.md](references/nips.md).
4. **Publish to the user's write relays, read from their read relays** (NIP-65 kind-10002 lists). Querying only one big relay is the #1 client bug. Fetch relay lists from a few indexer relays first.
5. **Verify before trusting**: check `id` matches the serialization and `sig` verifies, especially for kind 0/3/10002 and anything driving payments (zap receipts: verify the invoice actually paid — the event alone proves nothing).
6. **Replaceable ≠ deleted.** Updating kind 0/3 or an addressable event leaves the old version on some relays. NIP-09 deletion is a *request*; relays may honor it, mirrors won't.
7. `created_at` is client-supplied and untrusted. Use it for display ordering, never for security decisions.

## Quick sanity checks while coding

- Event id must be recomputed from fields, never trusted from input.
- `tags` is an array of arrays, not an object: `[["p", "<hex>"], ["e", "<id>", "<relay-hint>", "reply"]]`.
- bech32 (not bech32m) for all NIP-19 entities; npub/nsec/note are raw 32 bytes, nprofile/nevent/naddr are TLV.
- WebSocket relays speak text frames of JSON arrays; send one filter per REQ element, multiple filters in one REQ are OR'd.
- Subscription results are streaming: wait for `EOSE` before concluding a query is complete, and keep the sub open for live updates.
