---
name: nostr
description: Build, debug and operate Nostr clients, bots, relays and applications. Use for NIP-01 events and relay filters, public NIP-19 identifiers, NIP-07 and NIP-46 signing integration, relay operations, NIP-98 HTTP authentication and selecting NIPs for a concrete feature. Do not use for a simple request to look up the current wording or status of a NIP; use the nostr-nips companion skill for source-first specification research.
---

# Nostr engineering skill

## Activation and scope

Use this skill when implementing or operating Nostr clients, backends, bots, relays, event workflows, signers or relay queries.

Do not activate solely because a task mentions a NIP number or asks for the current status/text of a NIP. Use the companion nostr-nips skill for current specification research. Do not infer a protocol requirement from an implementation-specific behavior.

## Core event model

A Nostr event contains id, pubkey, created_at, kind, tags, content and sig. The event id is the SHA-256 hash of the NIP-01 serialized array [0, pubkey, created_at, kind, tags, content]. The signature is a BIP-340 Schnorr signature over the event id.

Important kinds include metadata (0), short text note (1), contacts (3), legacy DM (4), reposts (6/16), reaction (7), zap receipt (9735), relay list metadata (10002) and addressable long-form content (30023). Check references/kinds.md rather than guessing a kind.

Kind ranges: regular (stored as ordinary events), replaceable (10000–19999), ephemeral (20000–29999) and addressable/parameterized replaceable (30000–39999). For addressable events, the d tag participates in the replaceable address.

Client-to-relay messages include EVENT, REQ, CLOSE and AUTH. Relay-to-client messages include EVENT, EOSE, OK, NOTICE, CLOSED, COUNT and AUTH. NIP-01 filters support ids, authors, kinds, single-letter tag filters, since, until, limit and optional search capability.

## Task routing

| Task | Procedure |
|---|---|
| Encode/decode public NIP-19 references | Use scripts/nostr_key.py for npub, note, nprofile, nevent and naddr only. |
| Sign events or encrypt/decrypt NIP-44 | Use NIP-07, NIP-46 or a maintained, reviewed cryptographic library behind a dedicated signer. Never pass a secret key to a command-line argument or model context. |
| Query/publish to a relay or read NIP-11 | Use scripts/nostr_query.py; it accepts only ws/wss relay URLs resolving exclusively to public IPs, pins the TCP destination, disables environment proxies and does not follow NIP-11 redirects. Interpret its completeness field before treating a query as exhaustive. |

**Transport privacy limitation:** `scripts/nostr_query.py` connects directly to a validated public IP. It deliberately ignores environment proxy variables and does not support Tor `.onion` endpoints. Direct relay connections expose the client's network address to the relay; do not use this helper where Tor routing or anonymity is required. Use a separately audited Tor-aware transport with explicit remote-DNS and egress controls instead.
| Build a client, bot or app | Read references/client-dev.md. |
| Select a NIP or check deprecation/status | Read references/nips.md, then verify against the live canonical NIPs repository. |
| Look up event kinds or tag conventions | Read references/kinds.md and the current canonical NIPs source. |
| Install/configure/secure a relay | Read references/relay-ops.md. |

## Key custody and signing — mandatory security boundary

1. A secret nsec is account authority. Never ask the user to paste it into chat, store it in a skill, commit it, print it, log it, or put it in command-line arguments or shell history.
2. Do not use environment variables as the default secret transport for interactive agent work. Process environments may be exposed through diagnostics, crash reports or process inspection.
3. Browser clients should request signatures through NIP-07 or a wallet-provided signer. Cross-device/backend workflows should use NIP-46 or a dedicated signer/KMS/HSM with least-privilege policy and explicit authorization.
4. The agent may prepare and validate an unsigned event. It must not obtain or retain the signing secret. Require explicit user approval before publishing public or consequential events.
5. The previous custom pure-Python secp256k1/BIP-340 and NIP-44 implementation has been removed from scripts/nostr_key.py. The replacement utility only handles public NIP-19 identifiers and deliberately rejects nsec. Do not reintroduce private-key operations there.
6. Never describe a self-written cryptographic implementation as production safe because it passes test vectors. Secret-key operations require maintained, reviewed libraries and appropriate signer isolation.

## Protocol correctness rules

1. Recompute and verify event ids and signatures before trusting event data. A syntactically valid event is not automatically an authentic or truthful statement.
2. Treat kind 0, kind 3 and kind 10002 data as untrusted inputs. Validate schemas and relay URLs before using them. The bundled relay helper repeats public-destination checks, pins the actual TCP destination to the validated DNS result, disables ambient proxies and refuses NIP-11 redirects. Do not bypass those checks with a direct client connection from an agent.
3. NIP-04 is final but unrecommended/deprecated in favor of NIP-17. NIP-96 is draft and unrecommended, with Blossom (NIP-B7) as its replacement. Preserve legacy interoperability when required; do not call these specifications nonexistent or universally unsupported.
4. Use NIP-65 read/write relay metadata when appropriate. A single large relay is not a complete view of the network.
5. Updating a replaceable event does not guarantee every relay or mirror has removed the prior version. A NIP-09 deletion event is a request, not a universal erase guarantee.
6. created_at is supplied by the event author and must not be used as a security timestamp.
7. NIP-01 EOSE ends the initial stored-event phase; EOSE alone does not prove that every stored match was sent. Where supported, interpret NIP-67 EOSE hints: finish means definitive stored-result completion for the current authorization level, more means additional stored matches are available, and auth indicates that additional results may require NIP-42 AUTH. Ignore unknown hints. When finish and more are both absent—including legacy two-element EOSE—fall back to bounded until pagination using the oldest received created_at, as NIP-67 recommends. Keep completeness unknown unless a relay explicitly sends finish; do not promote legacy exhaustion to a complete result. The standalone relay helper bounds pagination to 10 pages by default. A repeated page, cursor failure or page-limit stop is reported incomplete. On timeout, CLOSED or connection failure, report partial/failed results rather than silently presenting them as complete.

## Implementation checks

- Tags are arrays of arrays, for example [["p", "<pubkey>"], ["e", "<event-id>", "<relay-hint>", "reply"]].
- NIP-19 uses bech32, not bech32m. npub, nsec and note carry 32-byte values; nprofile, nevent and naddr use TLV records.
- Multiple filters in one REQ are OR'd; do not assume AND semantics.
- Validate event id and signature with a maintained implementation. Verify payment receipts against the payment system; a zap receipt event alone does not prove that an invoice was paid.
- For relay search, check NIP-50 support and distinguish relay-specific search syntax from portable NIP-01 filtering.

## Source hierarchy

Use the canonical NIPs repository for specification status and normative wording, maintained implementations as secondary evidence, and articles/social posts only as supporting context. Record source URL, revision/date and whether a feature is draft, final, unrecommended, optional or implementation-specific when the distinction affects the implementation.
