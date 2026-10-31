# nostr-skill

Agent skill for building and operating on Nostr: event model, key handling, which NIP to use, client and relay work.

The skill file is [`SKILL.md`](SKILL.md). Long references live in `references/`. Two zero-dependency-ish tools live in `scripts/`:

| Script | Needs | Does |
|---|---|---|
| `scripts/nostr_key.py` | Python 3 stdlib | Keys, NIP-19, BIP340 sign/verify, NIP-44. `python3 scripts/nostr_key.py selftest` |
| `scripts/nostr_query.py` | `pip install websockets` | One-shot relay query, publish, NIP-11 |

Put secrets in `NOSTR_SECRET_KEY`. Pass `-` to the script. Do not put an nsec on the command line.

Companion skills, each in its own repo:

- [`nostr-nips`](https://github.com/NostrDanish/nostr-nips-skill) — fetch the current NIP text
- [`nak`](https://github.com/NostrDanish/nak-skill) — the nak CLI
- `blossom` — Blossom media (own repo; not part of this one)
- `nwc` — Nostr Wallet Connect (own repo; not part of this one)
- [`sip-01`](https://github.com/SIP-01/sip-01-skill) — kind 39697 web index

## Install

Copy this repo into the agent's skills directory (the folder that contains `SKILL.md` is the skill). Hermes:

```bash
git clone https://github.com/NostrDanish/nostr-skill.git
mkdir -p ~/.hermes/skills
ln -s "$PWD/nostr-skill" ~/.hermes/skills/nostr
```

Cursor and other Agent-Skills clients load `SKILL.md` from a skills path the same way.
