# Building Nostr clients, bots, and services

## Library choice by language

| Language | Library | When |
|---|---|---|
| TypeScript/JS | **nostr-tools** | Low-level, minimal deps; the reference implementation most docs assume |
| TypeScript/JS | **NDK** (@nostr-dev-kit/ndk) | Batteries-included: outbox model, signer abstraction, zaps, caching. Best default for apps |
| TypeScript/JS | **applesauce** (hzrd149) | Reactive/RxJS-style state, great for complex feeds |
| Rust | **nostr-sdk** (rust-nostr.org) | The Rust standard; bindings for Python, Kotlin, Swift, JS(wasm) |
| Go | **go-nostr** (fiatjaf) | Standard for Go; also base of khatru relays |
| Python | **nostr-sdk** (pip `nostr-sdk`, Rust bindings) | Best maintained option |
| Python | `pynostr` | Pure-python, simpler, less maintained |
| Kotlin/Swift | nostr-sdk bindings / **NDK**-style native libs | Mobile |

For quick scripts and CI: this skill's `scripts/nostr_key.py` + `scripts/nostr_query.py`
need nothing but Python stdlib (+ `websockets` for relay I/O).

## Signing strategy (decide first)

1. **Web app** → NIP-07 (`window.nostr.getPublicKey()`, `signEvent()`, `nip44.encrypt()`). Detect absence and request an explicit wallet action (for example Alby or nos2x); do not collect the raw nsec.
2. **Mobile/desktop app** → NIP-46 remote signer (`bunker://` or `nostrconnect://` connection established by the trusted wallet UI). Keep bunker secret material out of model context, command arguments, logs and ordinary app storage.
3. **Bot / backend** → a dedicated signer/KMS/HSM or isolated signer service with least-privilege policy. The bot/agent submits an unsigned event and receives a signed event; the agent never receives the raw nsec. Do not use an ordinary environment variable as the default key transport.
4. Never ask users to paste an nsec into a web form or chat. NIP-49 ncryptsec import/export belongs inside a trusted wallet/key-management UI, not an agent prompt or a shell pipeline.

## Minimal flows (nostr-tools v2 style)

```js
import { SimplePool } from 'nostr-tools'

const pool = new SimplePool()

// Pseudocode signer interface: supplied by NIP-07/NIP-46 or a dedicated signer.
// It does not expose a secret key to this process or to an agent.
const signer = appProvidedSigner
const pk = await signer.getPublicKey()

// Prepare an unsigned event, then request a signature through the trusted signer.
const unsigned = {
  kind: 1,
  content: 'gm',
  tags: [],
  created_at: Math.floor(Date.now() / 1000),
}
const signed = await signer.signEvent(unsigned)
await Promise.any(pool.publish(['wss://relay.damus.io', 'wss://nos.lol'], signed))

// Subscribe to public events. Validate signatures before trusting event authors.
const sub = pool.subscribeMany(['wss://relay.damus.io'], [{ kinds: [1], authors: [pk], limit: 20 }], {
  onevent(e) { /* verify before use */ },
  oneose() { /* stored phase ended; completeness may require NIP-67 */ },
})
```

The `signer` interface above is illustrative pseudocode; use the actual API supplied by the chosen wallet/NDK/NIP-46 client. Do not replace it with a locally generated secret key inside an agent task.

- Always publish to **multiple relays** (user's NIP-65 write list). `Promise.any` for first acceptance.
- Keep subscriptions bounded (`limit`, `since`), `CLOSE`/`sub.close()` them when done.
- Use `pool.querySync` / `pool.get` for one-shot fetches.

## The outbox model (NIP-65) — do this or be wrong

1. Bootstrap: query 2–4 well-known indexer relays (e.g. purplepag.es, relay.nos.social, nos.lol, relay.damus.io) for the target's **kind 10002**.
2. Read their events from their **read** relays; publish events tagging them to their **write** relays.
3. Cache kind 0 / 10002 / 10050 aggressively; refresh on staleness. Treat metadata and relay URLs as untrusted; validate destinations before connecting.
4. DMs (NIP-17): publish gift wraps to the recipient's **kind 10050** DM-inbox relays — a different list than 10002.

## Private DMs (NIP-17)

Flow per message: rumor (unsigned kind 14, real timestamp) → NIP-44-encrypt into seal (kind 13, signed by sender, randomized timestamp) → NIP-44-encrypt into gift wrap (kind 1059, signed by a random ephemeral key, randomized timestamp). Send one wrap addressed to recipient (+ optionally one to self). `nostr-tools/nip17`, NDK, and nostr-sdk all implement `wrapEvent/unwrapEvent` — use them; the double-wrap ordering is easy to get wrong.

## Zaps (NIP-57) in 6 steps

1. Fetch recipient kind 0 → `lud16`/`lud06` → LNURL pay endpoint (check `allowsNostr: true`).
2. Build an unsigned zap request: kind 9734, tags `p` (recipient), `e`/`a` (target), `relays`, `amount` (millisats); request the signature through the trusted signer.
3. GET `callback?amount=..&lnurl=..&nostr=<urlencoded zap request>` → bolt11 invoice.
4. Pay invoice via NWC (NIP-47), WebLN, or user wallet.
5. Receiver's LNURL server publishes kind 9735 receipt to the `relays` tag.
6. **Display rule**: a receipt is only proof if bolt11 paid AND receipt pubkey == recipient's lnurl `nostrPubkey`. Otherwise show as "unverified".

## Media upload (Blossom, NIP-B7)

1. sha256 the file; build kind 24242 auth event (`t` tag = `upload`, `x` tag = hash, `expiration`).
2. `PUT https://<blossom-server>/upload` with body = file, header `Authorization: Nostr <base64(auth-event)>`.
3. Response gives URL (usually `/<sha256>.<ext>`). Reference in notes directly, or in kind 1063/`imeta` tags.
Servers: blossom servers are per-user (kind 10063 server list). Legacy NIP-96 hosts still exist; treat Blossom as default.

## NIP-98 HTTP auth for your own API

Client: prepare an unsigned kind 27235 event with tags `["u", absolute-url]`, `["method", "POST"]`, `["payload", sha256-of-body]` (if body), and current `created_at`; sign it through the trusted signer, then base64 the signed event into `Authorization: Nostr <b64>`.
Server: decode, verify sig, check `u`+`method` match, `|created_at - now| < 60s`, optionally payload hash. Replay-cache event ids for the window.

## Performance & correctness checklist

- Verify signatures at ingestion (or use pool/SDK verification), then trust your own cache.
- Deduplicate by event id across relays.
- Addressable queries: `{"kinds":[30023], "authors":[pk], "#d":["slug"]}`.
- Pagination: set `until` = oldest seen `created_at - 1`, repeat.
- `limit` applies per-filter per-relay; merging N relays needs client-side trim.
- WebSocket hygiene: one socket per relay, multiplex subs, exponential backoff, respect `CLOSED`/`NOTICE` (auth-required, rate-limited, blocked).
- Ephemeral kinds (20k–29k) never arrive from history — only live subs.
- Don't render raw `content` as HTML; escape everything. Nostr is a spam-rich environment.

## Testing without the live network

- Local relay in seconds: `docker run --rm -p 8080:8080 scsibug/nostr-rs-relay` or `khatru` example binaries; strfry for heavier use.
- `nak` (fiatjaf's CLI) is useful for read-only debugging: `nak req -k 1 -l 5 wss://...`, `nak decode npub1...`. The version used in this skill set is v0.22.3; install a pinned release, not `@latest`. For publishing, use an already-signed event or a trusted signer workflow; never pass a secret with `--sec` or ask an agent to use `--prompt-sec`.
- Web inspectors: nostr-debug (relays), njump.me, nostr.at / iris.to for viewing events by nevent/note.
