# Relay and query failure modes

Use this when a query returns nothing, a publish is rejected, or a client
looks "broken" but the event is valid.

## Empty result after EOSE

1. Wrong relay. Fetch the author's kind `10002` (and kind `10050` for DMs) from
   a couple of indexer relays first. Query write relays for their notes, read
   relays for what they want to see.
2. Filter too tight. `ids`/`authors` prefixes are hex prefixes, not npubs.
   `#e`/`#p`/`#d` keys must be the single-letter form (`"#e"`).
3. Kind lifecycle. Replaceable/addressable: you only get the newest. Ephemeral
   kinds (20000–29999) are never stored — you will not `REQ` them back later.
4. Auth-required. A `CLOSED` with `auth-required:` means send NIP-42 AUTH
   (`scripts/nostr_query.py` does **not** implement AUTH; use `nak req --auth`
   or a real client).

## CLOSED / NOTICE / OK false

| Relay message | Meaning | What to do |
|---|---|---|
| `CLOSED` `auth-required:…` | NIP-42 | Authenticate; this script cannot |
| `CLOSED` `restricted:…` / `blocked:…` | policy | Different relay, or the pubkey is banned |
| `CLOSED` `error:…` / `pow:…` | filter or POW | Fix filter; add NIP-13 nonce if required |
| `NOTICE` | human hint | Read it; do not retry blindly |
| `OK` false `duplicate:` | already have it | Success for the publisher |
| `OK` false `pow:` / `rate-limited:` | policy | Back off; do not tight-loop |
| `OK` false `invalid:` / `blocked:` | bad event | Recompute id, verify sig, check kind/tags |

## Publish accepted but invisible

- You published to a write relay the reader does not query. Attach relay hints
  on `nevent`/`naddr`/`nprofile`, and publish to 2+ relays including one the
  audience already uses.
- Replaceable collision: a newer `created_at` for the same pubkey+kind (`d`
  for addressable) replaced yours on that relay.
- `created_at` in the future is dropped by many relays.

## Verify before acting

`scripts/nostr_query.py query --verify` drops events whose `id` or `sig` fail.
Still verify zap receipts against the invoice — a valid signature does not
mean the invoice paid.
