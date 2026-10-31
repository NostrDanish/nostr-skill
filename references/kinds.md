# Event kinds quick reference

Aligned with NIP-01 kind ranges and the NIPs README (checked Oct 2026). For
canonical live text, load `nostr-nips` and fetch
`https://raw.githubusercontent.com/nostr-protocol/nips/master/README.md`.

## Ranges (NIP-01)

| Range | Class | Semantics |
|---|---|---|
| `0`, `3` | replaceable | newest per pubkey+kind (legacy exceptions outside 10000–19999) |
| all other `n < 10000` | regular | stored; all versions kept |
| `10000–19999` | replaceable | newest per pubkey+kind |
| `20000–29999` | ephemeral | never stored; live-only |
| `30000–39999` | addressable | newest per pubkey+kind+`d` tag |

Kind `2` (recommend relay) is **regular** and deprecated — use kind `10002`.
Kind `41` is **regular** NIP-28 channel metadata (NIP-28 itself is unrecommended).
Neither `2` nor `41` is addressable.

## Regular kinds

| Kind | Use |
|---|---|
| 1 | short text note (NIP-10 threading) |
| 2 | recommend relay (deprecated; use kind 10002) |
| 4 | legacy encrypted DM — DO NOT USE (NIP-17 instead) |
| 5 | deletion request (NIP-09; `e`/`a`/`k` tags) |
| 6 | repost of kind 1 · **7** reaction (`+`/`-`/emoji) · **8** badge award |
| 9 | chat message (NIP-C7) · **11** forum thread (NIP-7D) |
| 13 | seal (NIP-59) · **14** DM rumor (unsigned, inside seal) · **15** file message (NIP-17) |
| 16 | generic repost (any kind) |
| 17 | reaction to a website |
| 20 | picture (NIP-68) · **21** video · **22** short video (NIP-71) |
| 24 | public message (NIP-A4) |
| 40–44 | NIP-28 channels (unrecommended; prefer NIP-29) |
| 62 | request to vanish (NIP-62) |
| 1063 | file metadata (NIP-94: url, m mime, x sha256, size, dim) |
| 1111 | comment (NIP-22) |
| 1311 | live chat message (NIP-53) |
| 1617 | git patch · **1618** git PR · **1621** git issue · **1630–1633** git status (NIP-34) |
| 1984 | report (NIP-56) · **1985** label (NIP-32) |
| 2003 | torrent (NIP-35) |
| 4550 | community post approval (NIP-72, unrecommended) |
| 9000–9030 | NIP-29 group moderation |
| 9321 | nutzap (NIP-61) |
| 9734 | zap request · **9735** zap receipt (NIP-57) |

## Replaceable (kind 0, 3, and 10000–19999)

| Kind | Use |
|---|---|
| 0 | profile metadata (JSON: name, about, picture, nip05, lud16, banner…) |
| 3 | follows (NIP-02; `["p", hex, relay?, petname?]`) |
| 10000 | mute list · **10001** pin list · **10002** relay list (NIP-65: `["r", url, "read" or "write"]`) |
| 10003 | bookmarks · **10004** communities · **10005** public chats · **10006** blocked relays |
| 10007 | search relays · **10009** group list (NIP-51/29) · **10012** favorite relays |
| 10013 | private-outbox / draft relays · **10015** interests · **10019** nutzap mint info (NIP-61) |
| 10020 | media follows · **10030** emoji list · **10050** DM inbox relays (NIP-17) |
| 10051 | key-package relays (Marmot) · **10063** Blossom server list (NIP-B7) |
| 13194 | NWC info (NIP-47) · **17375** Cashu wallet (NIP-60) |

## Ephemeral (20000–29999)

22242 auth (NIP-42) · 23194/23195 NWC request/response (NIP-47) · 24133 Nostr Connect (NIP-46) · 24242 Blossom blob auth (NIP-B7) · 27235 HTTP auth (NIP-98)

## Addressable (30000–39999) — all need a `d` tag

| Kind | Use |
|---|---|
| 30000 | follow sets · **30002** relay sets · **30003** bookmark sets |
| 30004 | curation sets · **30005** video sets · **30008** profile badges · **30009** badge definition |
| 30015 | interest sets · **30023** long-form article (NIP-23; `title`, `image`, `summary`, `published_at`) |
| 30024 | draft long-form · **30030** emoji sets · **30040** curated publication index · **30041** publication content |
| 30063 | release artifact sets (NIP-34) · **30078** app-specific data (NIP-78) |
| 30166 | relay discovery (NIP-66: `["d", relay-url]` + NIP-11 fields) |
| 30267 | app curation sets · **30311** live event (NIP-53) · **30315** user status (NIP-38) |
| 30383 | NIP-85 trusted-assertion events |
| 30402 | classified listing (NIP-99) · **30403** draft classified |
| 30617 | git repository announcement (NIP-34) · **30618** repo state |
| 30818 | wiki article (NIP-54) |
| 31234 | draft event (NIP-37, NIP-44-encrypted content) |
| 31922 | date-based calendar · **31923** time-based · **31924** calendar · **31925** RSVP (NIP-52) |
| 31989 | handler recommendation · **31990** handler information (NIP-89) |
| 34550 | community definition (NIP-72, unrecommended) · **39000–39009** group metadata (NIP-29) |

## Tag conventions worth memorizing

- `e` (event ref): `["e", id, relayHint?, marker?]` — markers: `root`/`reply`/`mention` (NIP-10)
- `p` (pubkey ref): `["p", hex, relayHint?, petname?]`
- `a` (address ref): `["a", "kind:pubkey:d-identifier", relayHint?]`
- `d`: identifier for addressable events · `t`: hashtag (lowercase)
- `r`: reference/relay URL · `imeta`: media metadata key-value pairs
- `amount`+`bolt11`+`preimage`+`description` on zap receipts · `expiration` (NIP-40) · `nonce`+difficulty (NIP-13)
- `content-warning` (NIP-36) · `subject` (NIP-14) · `-` protected (NIP-70) · `proxy` (NIP-48) · `emoji` (NIP-30)
