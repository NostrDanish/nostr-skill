# nostr-skill

Agent skill for building, debugging, and operating on the Nostr protocol: event model, key handling, NIP choice, client libraries, and relay setup.

The procedure lives in `SKILL.md`. Longer notes are loaded only when the task needs them:

| Path | Use |
|---|---|
| `scripts/nostr_key.py` | Zero-dependency keys, NIP-19, BIP340 sign/verify, NIP-44. Pass `-` as the key so it reads `NOSTR_SECRET_KEY`. |
| `scripts/nostr_query.py` | One-off relay query, publish, and NIP-11 fetch (`pip install websockets`). |
| `references/client-dev.md` | Libraries, signers, outbox, DMs, zaps, media, NIP-98. |
| `references/nips.md` | Which NIP to use, and which are deprecated. |
| `references/kinds.md` | Kind numbers and tag shapes. |
| `references/relay-ops.md` | strfry, khatru, nostr-rs-relay. |

Live spec text is the companion [nostr-nips skill](https://github.com/NostrDanish/nostr-nips-skill). The `nak` CLI has its own skill. Blossom uploads have their own skill.

## Install

Copy this directory into the agent's skills folder, or point the agent at `SKILL.md`.

An nsec never belongs in this repo, in a command argument, or in a chat log. Bots read `NOSTR_SECRET_KEY` from the environment.
