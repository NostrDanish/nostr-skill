# Running a Nostr relay

## Pick an implementation

| Relay | Lang / DB | Best for |
|---|---|---|
| **strfry** | C++ / LMDB | High-traffic public relays; the performance king. Powers most big relays |
| **khatru** | Go library | Custom relays in ~50 lines of Go (policy hooks, ACLs). Base of pyramid, khatru29 |
| **nostr-rs-relay** | Rust / SQLite | Small community or personal relay, low resource |
| **haven** | Go | Opinionated personal relay: inbox/outbox, private+trusted spaces, Blossom built in |
| **nostream** | TS / Postgres | Familiar stack for JS shops; heavier |
| **WoT relay** | — | Web-of-trust filtered relay (rank by social graph) |

## Minimal strfry setup (Debian/Ubuntu)

```bash
git clone https://github.com/hoytech/strfry && cd strfry
git submodule update --init && make setup-golpe && make -j$(nproc)
sudo cp strfry /usr/local/bin/
# edit strfry.conf: db dir, bind 127.0.0.1:7777, max connections
strfry relay   # run under systemd in production
```

Put **Caddy or nginx in front** for TLS (relays are WebSocket: `wss://` requires valid TLS; Caddy auto-HTTPS is the path of least resistance). Reverse-proxy `/` → `127.0.0.1:7777` with Upgrade headers. Docker alternative: `docker compose` images exist for strfry + Caddy.

Relay Runner (relayrunner.org) has per-implementation step-by-step guides — consult for full builds.

## Configuration decisions that matter

1. **Write policy**: fully open relays drown in spam within days. Options: NIP-42 auth + pubkey allowlist, paid admission (LN), PoW minimum (NIP-13), WoT scoring, or read-only mirror.
2. **NIP-11 relay document**: set `name`, `description`, `pubkey` (operator), `contact`, `supported_nips`, `software`, `version`, limitation fields (`max_message_length`, `max_subscriptions`, `max_filters`, `max_limit`, `auth_required`, `payment_required`). Clients and relay-discovery (NIP-66 monitors) read this.
3. **Retention**: strfry `relay.info`-level filters + periodic `strfry delete`/export; consider auto-expiring kinds via NIP-40 and dropping kind 1059 older than X days.
4. **Limits**: cap `max_limit` (e.g. 5000), message size (~128–512KB), subscription count per IP.
5. **Backups**: LMDB dir copy while stopped, or `strfry export` → newline-JSON. Restore with `strfry import`.

## NIP-42 auth flow (implement/enforce)

Relay sends `["AUTH", "<challenge>"]` on connect or on restricted REQ/EVENT. Client replies `["EVENT", {kind: 22242, tags: [["relay", relay-url], ["challenge", challenge]], ...}]`. Relay validates sig, `relay` tag matches its own URL, challenge matches, `created_at` recent. Use `["OK", id, false, "auth-required: ..."]` / `["CLOSED", sub, "auth-required: ..."]` to trigger it on demand.

## Management & moderation

- **NIP-86** (supported by strfry, khatru): admin RPC events (kind 13534 responses; methods like `banpubkey`, `allowpubkey`, `banevent`, `changerelayname`) sent over the relay's own WS from an admin pubkey.
- strfry local CLI: `strfry scan`, `strfry delete --filter`, `strfry dict` — for one-off moderation.
- Reject-list basics: known-bad pubkeys, illegal-content hashes; publish your policy in NIP-11.

## Syncing relays (negentropy / NIP-77)

strfry has built-in negentropy set-reconciliation (`strfry sync wss://other-relay` or persistent sync config) — bandwidth-efficient mirroring without full filters. khatru ships `negentropy` storage hooks. Use for: backup relays, inbox/outbox pairs, community mirrors. Plain REQ-based backfill works for small sets but doesn't scale.

## Special-purpose relay patterns

- **Inbox/outbox personal relay** (NIP-65/17): haven, or strfry with allowlist = you + friends; advertise as write/read relay in your kind 10002.
- **NIP-29 group relay**: khatru29 or strfry29 — relay enforces group membership/moderation kinds (9000s/39000s) itself.
- **Search relay**: strfry + NIP-50 search plugin (strfry search plugin) or nostr-rs-relay forks with full-text.
- **Tor relay**: strfry binds locally; expose via a tor hidden service; advertise the `.onion` URL (clients like Amethyst support it).

## Operational gotchas

- WebSocket proxies: must pass `Upgrade`/`Connection` headers and allow long-lived idle connections (raise nginx `proxy_read_timeout`).
- Clients hammer with reconnects — rate-limit per IP at the proxy, not just the relay.
- Clock skew breaks NIP-42 and NIP-98 (`created_at` windows) — run NTP.
- LMDB `mapsize` (strfry) must be pre-sized generously (e.g. 1TB virtual); it's virtual, not allocated.
- Monitor with a NIP-66 monitor (e.g. nostr.watch) to see how the network views your relay.
