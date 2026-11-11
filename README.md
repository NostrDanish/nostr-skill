# Nostr Skill

Portable Agent Skill for implementing and operating Nostr clients, relays, bots and applications.

## Install

Clone this repository into a folder named `nostr` inside your agent's skills root. The folder name must match the `name: nostr` frontmatter value.

~~~bash
git clone https://github.com/NostrDanish/nostr-skill <skills-root>/nostr
~~~

## Security boundary

The included `scripts/nostr_key.py` is now a public-only NIP-19 codec. It handles public references such as `npub`, `note`, `nprofile`, `nevent` and `naddr`; it deliberately refuses `nsec`. Secret-key generation, signing and NIP-44 cryptography have been removed from this script.

Use NIP-07, NIP-46 or a maintained, reviewed cryptographic library behind a dedicated signer. Never pass an nsec through command-line arguments, shell history, model context, logs or ordinary stdout.

The relay query helper reports completeness explicitly. EOSE without a NIP-67 `finish` hint is unknown; `more` means additional stored results are available; `auth` may require NIP-42 authentication; and timeouts/CLOSED are not complete results.

## Contents

- `SKILL.md` — Nostr implementation and operating guidance.
- `references/` — client development, kinds, NIPs and relay operations.
- `scripts/nostr_key.py` — public-only NIP-19 codec.
- `scripts/nostr_query.py` — relay query/publish and NIP-11 inspection.
- `tests/test_nostr_key.py` — public NIP-19 safety regression tests.

## Tests

Python 3.11+ is required for the test environment.

~~~bash
python -m unittest discover -s tests -v
python -m py_compile scripts/nostr_key.py scripts/nostr_query.py
~~~

## License

See the repository's license file.
