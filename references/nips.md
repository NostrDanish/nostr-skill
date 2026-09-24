# NIP guide — which spec to reach for (status as of Sep 2026)

Canonical source: https://github.com/nostr-protocol/nips — check it for anything
not listed here; new NIPs appear constantly and statuses change.

## The essential dozen (implement these first)

| NIP | What | Notes |
|---|---|---|
| 01 | Basic protocol: events, kinds, filters, wire messages | Everything builds on this |
| 19 | bech32 entities: npub/nsec/note/nprofile/nevent/naddr | bech32, NOT bech32m |
| 05 | DNS identifiers (`alice@domain.com` → pubkey via `/.well-known/nostr.json`) | Verification is one-way; don't treat as strong identity |
| 07 | `window.nostr` browser extension signing | Default signer for web apps |
| 10 | Threading: `e`/`p` tag conventions (root/reply/mention markers) | Positional `#[n]` mentions (NIP-08) are dead — use NIP-27 |
| 25 | Reactions (kind 7, `+`/`-`/emoji) | |
| 18 | Reposts (kind 6, generic repost kind 16) | |
| 65 | Relay list metadata (kind 10002, r/w markers) — the **outbox model** | The backbone of relay selection |
| 44 | Versioned encryption (ChaCha20 + HKDF + HMAC, conversation key from ECDH) | Use for all new private payloads |
| 17 | Private DMs = NIP-44 sealed kinds 13/14 inside NIP-59 gift wraps (kind 1059) | Replaces NIP-04; hides metadata via random timestamps |
| 57 | Lightning zaps (kinds 9734 request / 9735 receipt, lud16 LNURL flow) | Verify receipt's bolt11 against the invoice; receipts are forgeable otherwise |
| 98 | HTTP auth: kind 27235 event in `Authorization: Nostr <base64>` header | For APIs, Blossom, NIP-96-era servers |

## Common features

- **02** contact list (kind 3, petnames) · **09** deletion requests (kind 5) · **11** relay info document (`Accept: application/nostr+json`)
- **13** proof of work (`nonce` tag) · **14** subject tag · **21** `nostr:` URI scheme · **22** comments (kind 1111, uppercase/lowercase tag pairs)
- **23** long-form markdown (kind 30023, `d` tag) · **24** extra profile fields · **27** inline `nostr:` references
- **29** relay-based groups (kinds 9000s admin, 39000s metadata; chat kind 9/10/11/12) · **30** custom emoji (`emoji` tag + kind 10030/30030)
- **32** labels (kind 1985, `L`/`l` tags) · **34** git over nostr (repos kind 30617, patches 1617, PRs 1618, issues 1621) · **36** sensitive content (`content-warning`)
- **37** drafts (kind 31234, NIP-44 encrypted to self) · **38** user statuses (kind 30315) · **40** expiration (`expiration` tag)
- **42** client→relay auth (kind 22242) · **45** `["COUNT", ...]` · **46** Nostr Connect remote signing (`bunker://`, kind 24133)
- **47** Nostr Wallet Connect (kinds 13194/23194-23197) · **50** search (`search` filter field, relay-optional)
- **51** lists: mute/pin/bookmarks/relays/interests (kinds 10000-10003 standard, 30000-30003 sets, follow sets 30000) · **52** calendar (kinds 31922-31925)
- **53** live activities (kind 30311, chat 1311) · **56** reports (kind 1984) · **58** badges (30009/8/30008)
- **59** gift wrapping (kind 1059, random timestamp ±2 days) · **62** right to vanish (kind 62) · **70** protected events (`-` tag, relay-gated)
- **71** video events (kinds 21/22, `imeta` tag) · **72** moderated communities (kind 34550, posts 11 with `a` tag) · **73** external content IDs
- **75** zap goals (kind 9041) · **78** app data (kind 30078) · **84-87** highlights/curation · **86** relay management API (kind 13534 etc.)
- **88** NUT-zaps (Cashu ecash) · **89** recommended app handlers (kinds 31989/31990) · **90** data vending machines (kinds 5000-5999 requests, 6000-6999 results)
- **94** file metadata (kind 1063) · **99** classified listings (kind 30402) · **A0** voice messages · **B7** Blossom media servers · **C0** code snippets · **C7** chats (kind 9-based) · **F4** podcasts

## Deprecated / unrecommended — do NOT build on these

| NIP | Was | Use instead |
|---|---|---|
| 04 | Encrypted DMs (kind 4, leaky ECDH) | **NIP-17** |
| 06 | BIP39 mnemonic key derivation | single nsec |
| 08 | `#[index]` mentions | **NIP-27** `nostr:` references |
| 15 | Marketplace (stalls/products) | **NIP-99** classifieds |
| 26 | Delegated event signing | NIP-46 remote signing |
| 28 | Public chat channels | **NIP-29** groups |
| 03, 31 | OpenTimestamps, unknown-event `alt` handling | (niche; NIP-31's `alt` convention still widely used informally) |
| 96 | HTTP file storage | **Blossom (NIP-B7)** |
| EE | MLS E2EE messaging | **Marmot Protocol** (MDK) |

## Key management guidance

- nsec = raw 32-byte secret, bech32 `nsec1...`. npub = x-only pubkey.
- Browser: NIP-07. Mobile/2FA: NIP-46 bunker. Server bot: nsec in env var.
- NIP-49 (`ncryptsec1...`) password-encrypts an nsec for backup.
- Key rotation doesn't exist — compromise means migrating followers to a new key with a kind-0/3 announcement from both keys.
