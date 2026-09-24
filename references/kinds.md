# Event kinds quick reference

## Ranges (NIP-01 §kinds)

| Range | Class | Semantics |
|---|---|---|
| 0, 3, 41, 1000–9999 | regular | stored, all versions kept |
| 10000–19999 (incl. 0, 3) | replaceable | per pubkey+kind, keep newest only |
| 20000–29999 | ephemeral | never stored, live-only |
| 30000–39999 (incl. 2, 41) | addressable | per pubkey+kind+`d` tag, keep newest |

n=2 and n=41 exceptions aside: 0 metadata and 3 contacts are *replaceable*.

## Regular kinds

| Kind | Use |
|---|---|
| 0 | profile metadata (JSON: name, about, picture, nip05, lud16, banner...) |
| 1 | short text note (NIP-10 threading) |
| 2 | recommend relay (deprecated-ish; use kind 10002) |
| 3 | follows (NIP-02 contact list; `["p", hex, relay?, petname?]`) |
| 4 | legacy encrypted DM — DO NOT USE (NIP-17 instead) |
| 5 | deletion request (NIP-09; `e`/`a`/`k` tags) |
| 6 | repost of kind 1 · **7** reaction (`+`/`-`/emoji) · **8** badge award |
| 9 | group chat message (NIP-29) · **10** group threaded reply · **11** group thread / community post (NIP-72) · **12** group reply |
| 13 | seal (NIP-59) · **14** DM rumor base kind (unsigned, inside seal) |
| 16 | generic repost (any kind) |
| 17 | reaction to a website |
| 20 | picture (first-clients) · **21** video normal · **22** short video (NIP-71) |
| 40–43 | NIP-28 channels (dead) |
| 62 | request to vanish (NIP-62) |
| 1063 | file metadata (NIP-94: url, m mime, x sha256, size, dim) |
| 1111 | comment (NIP-22) |
| 1311 | live chat message (NIP-53) |
| 1617 | git patch · **1618** git PR · **1621** git issue · **1630–1633** git status (NIP-34) |
| 1984 | report (NIP-56) · **1985** label (NIP-32) |
| 1986 | relay reviews (niche) · **1987** AI embeddings (niche) |
| 2003 | torrent (NIP-35) · **2022** coinjoin (niche) |
| 4550 | community post approval (NIP-72) |
| 5000–5999 | DVM job requests (NIP-90: 5050 text gen, 5100-5199 misc, 5200-5299 image/video, 5300+ discovery) |
| 6000–6999 | DVM results · **7000** DVM feedback (payment-request, status) |
| 9000–9030 | NIP-29 group moderation (put-user, remove-user, edit-metadata, delete-event, create/delete group...) |
| 9734 | zap request · **9735** zap receipt (NIP-57) |
| 10000–30003 | see lists below |
| 23194 | NWC request · **23195** NWC response · **13194** NWC info (NIP-47) |
| 24133 | Nostr Connect (NIP-46) |
| 27235 | HTTP auth (NIP-98; must have `u` and `method` tags, created_at ±60s) |
| 30000–39999 | addressable (below) |

## Replaceable (10000–19999)

| Kind | Use |
|---|---|
| 10000 | mute list · **10001** pin list · **10002** relay list (NIP-65: `["r", url, "read"\|"write"]`) |
| 10003 | bookmarks · **10004** communities · **10005** public chats · **10006** blocked relays |
| 10007 | search relays · **10009** group list (NIP-51/29) · **10012** favorite relays |
| 10013 | private-outbox relays · **10015** interests · **10019** nutzap info (NIP-61) |
| 10020 | media follows · **10030** emoji list · **10050** DM inbox relays (NIP-17!) |
| 10051 | key-package relays (Marmot/MLS) · **10102** good wiki relays (NIP-54) |
| 13194 | NWC info (NIP-47) · **17375** Cashu wallet (NIP-60) |

## Ephemeral (20000–29999)

22242 auth (NIP-42) · 23194/23195 NWC req/resp (NIP-47) · 24133 Nostr Connect (NIP-46) · 21000 lightning RPC (niche)

## Addressable (30000–39999) — all need a `d` tag

| Kind | Use |
|---|---|
| 30000 | follow sets · **30001** generic lists (deprecated → 30003) · **30002** relay sets · **30003** bookmark sets |
| 30004 | interest sets · **30005** emoji sets · **30008** profile badges · **30009** badge definition |
| 30015 | interest sets (alt) · **30017** stall / **30018** product (NIP-15, dead) |
| 30023 | long-form article (NIP-23; `title`, `image`, `summary`, `published_at`) |
| 30024 | draft long-form · **30030** emoji sets (alt) · **30040** curated publication index · **30041** publication content |
| 30063 | release artifact sets (NIP-34) · **30078** app-specific data (NIP-78) |
| 30166 | relay discovery (NIP-66: `["d", relay-url]` + NIP-11 fields) |
| 30267 | app curation sets · **30311** live event (NIP-53) · **30312** interactive room (niche) · **30315** user status (NIP-38) |
| 30383 | NIP-85 trusted-assertion provider events |
| 30402 | classified listing (NIP-99) · **30403** draft classified |
| 30617 | git repository announcement (NIP-34) · **30618** repo state |
| 30818 | wiki article (NIP-54) |
| 31234 | draft event (NIP-37, NIP-44-encrypted content) |
| 31890 | feed (DVM) · **31922** date-based calendar event · **31923** time-based · **31924** calendar · **31925** RSVP (NIP-52) |
| 31989 | handler recommendation · **31990** handler information (NIP-89) |
| 34550 | community definition (NIP-72) · **39000–39009** group metadata/membership (NIP-29) |

## Tag conventions worth memorizing

- `e` (event ref): `["e", id, relayHint?, marker?]` — markers: `root`/`reply`/`mention` (NIP-10)
- `p` (pubkey ref): `["p", hex, relayHint?, petname?]`
- `a` (address ref): `["a", "kind:pubkey:d-identifier", relayHint?]`
- `d`: identifier for addressable events · `t`: hashtag (lowercase)
- `r`: reference/relay URL · `imeta`: media metadata key-value pairs
- `amount`+`bolt11`+`preimage`+`description` on zap receipts · `expiration` (NIP-40) · `nonce`+difficulty (NIP-13)
- `content-warning` (NIP-36) · `subject` (NIP-14) · `-` protected (NIP-70) · `proxy` (NIP-48) · `emoji` (NIP-30)
