# nostr-skill

Agent skill for building, debugging, and operating on the Nostr protocol: events, keys, NIPs, relays, and the rules that are easy to get wrong.

`SKILL.md` is the procedure. Long tables live in `references/`. Two stdlib-first tools:

```bash
python3 scripts/nostr_key.py selftest
python3 scripts/nostr_query.py selfcheck          # no network
pip install websockets                            # only for query/publish
```

Secrets go in `NOSTR_SECRET_KEY`. Pass `env` to `nostr_key.py` and `-` to read event JSON from stdin. Do not put an nsec on the command line.

## What this skill will not pretend to be

- Live NIP text is the `nostr-nips` skill. The tables here are a map.
- The `nak` CLI is the `nak` skill. With no key set, nak signs as the public default key `01`.
- Blossom uploads are the `blossom` skill (kind 24242, base64url).
- NIP-90 DVMs are the `nostr-dvm` skill, and that NIP is marked unrecommended.

## Install

Copy this repo into the agent's skills directory, or point the agent at `SKILL.md`.

Production apps should call an audited library (`nostr-tools`, NDK, nostr-sdk). These scripts are for agents and one-off tooling.
