# nostr-skill

Agent skill for building, debugging, and operating anything on the [Nostr](https://github.com/nostr-protocol/nips) protocol: keys, BIP340 signing, NIP-19/44, relay queries, client development, and relay ops.

This is the **offline toolkit**. For live NIP text use [nostr-nips-skill](https://github.com/NostrDanish/nostr-nips-skill). For CLI debugging use [nak-skill](https://github.com/NostrDanish/nak-skill). For kind 39697 web-index events use [sip-01-skill](https://github.com/SIP-01/sip-01-skill).

## Layout

```
SKILL.md                 always-on protocol model, rules, task routing
scripts/nostr_key.py     zero-dep keys, bech32, sign/verify, NIP-44 (stdlib)
scripts/nostr_query.py   relay query / publish / NIP-11 (needs websockets)
references/kinds.md      kind and tag cheat sheet
references/nips.md       which NIP to reach for (snapshot; refresh via nostr-nips)
references/client-dev.md libraries, signers, DMs, zaps, media
references/relay-ops.md  strfry / khatru / nostr-rs-relay
```

## Quick start

```bash
python3 scripts/nostr_key.py gen
python3 scripts/nostr_key.py selftest
python3 scripts/nostr_key.py sign "$NSEC" '{"kind":1,"content":"hi","tags":[],"created_at":1700000000}'
pip install -r requirements.txt
python3 scripts/nostr_query.py query wss://relay.damus.io '{"kinds":[1],"limit":3}'
```

Install: copy `SKILL.md`, `scripts/`, and `references/` into your agent skill library (Hermes: `~/.hermes/skills/nostr/`).

## License

CC-BY-SA-4.0
