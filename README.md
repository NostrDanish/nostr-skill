# nostr-skill

Offline toolkit for building, debugging, and operating Nostr clients, bots,
relays, and keys. Load this skill when the task involves events, keys,
filters, signing, or relay ops.

Companion skills (do not fold their jobs into this one):

| Skill | Use instead when |
|---|---|
| [nostr-nips](https://github.com/NostrDanish/nostr-nips-skill) | You need **live** NIP text or the current kind registry |
| [nak](https://github.com/NostrDanish/nak-skill) | The `nak` CLI is installed and you want its query/publish/git flows |
| [sip-01](https://github.com/SIP-01/sip-01-skill) | Kind 39697 web-index observations |

## Layout

```
SKILL.md                  core model, routing, non-negotiable rules
references/kinds.md       kind ranges + common kinds/tags
references/nips.md        offline NIP routing snapshot
references/client-dev.md  libraries, signers, DMs, zaps, outbox
references/relay-ops.md   strfry / khatru / nostr-rs-relay
references/failure-modes.md  CLOSED / empty EOSE / auth-required
scripts/nostr_key.py      stdlib keys, NIP-19, sign/verify, NIP-44
scripts/nostr_query.py    one-off REQ / EVENT / NIP-11 (needs websockets)
```

## Scripts

```bash
python3 scripts/nostr_key.py selftest
python3 scripts/nostr_key.py gen
python3 scripts/nostr_key.py sign "$NSEC" - < unsigned.json
pip install websockets
python3 scripts/nostr_query.py query --verify wss://relay.damus.io '{"kinds":[1],"limit":3}'
```

`nostr_key.py` is stdlib-only. Never log or commit an nsec.

## Install

Copy or symlink this repo into the agent's skills directory (Hermes:
`~/.hermes/skills/nostr`; Cursor: `.cursor/skills/nostr` or a plugin path).
The skill is the folder that contains `SKILL.md`.
