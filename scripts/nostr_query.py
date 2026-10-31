#!/usr/bin/env python3
"""nostr_query.py — query and publish to Nostr relays over WebSocket.

Requires: pip install websockets

CLI:
  python3 nostr_query.py selfcheck
  python3 nostr_query.py query wss://relay.damus.io '{"kinds":[1],"limit":5}'
  python3 nostr_query.py info wss://relay.damus.io
  python3 nostr_query.py publish wss://relay.damus.io '<signed-event-json>'
  python3 nostr_query.py publish wss://relay.damus.io -   # event JSON on stdin

`ids`, `authors`, `#e` and `#p` must be full 64-character lowercase hex.
NIP-01 no longer allows prefixes.

If the relay sends AUTH or `auth-required` and NOSTR_SECRET_KEY is set, this
answers with a kind-22242 AUTH event (NIP-42). The key is never printed.
Received events are signature-checked; failures are reported on stderr and
the process exits 2 if any event failed verification.
"""
import asyncio
import importlib.util
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def _nostr_key():
    path = Path(__file__).with_name("nostr_key.py")
    spec = importlib.util.spec_from_file_location("nostr_key", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _auth_event(relay, challenge):
    raw = os.environ.get("NOSTR_SECRET_KEY", "").strip()
    if not raw:
        return None
    nk = _nostr_key()
    return nk.sign_event(
        {
            "kind": 22242,
            "created_at": int(time.time()),
            "tags": [["relay", relay], ["challenge", challenge]],
            "content": "",
        },
        nk._resolve_seckey(raw),
    )


async def _send_auth(ws, relay, challenge):
    ev = _auth_event(relay, challenge)
    if ev is None:
        print("relay requires AUTH and NOSTR_SECRET_KEY is not set", file=sys.stderr)
        return False
    await ws.send(json.dumps(["AUTH", ev]))
    return True


def _check(ev):
    try:
        return _nostr_key().verify_event(ev)
    except Exception:
        return False


async def query(relay, filter_json, timeout=15):
    import websockets

    filt = json.loads(filter_json)
    events = []
    challenge = None
    authed = False
    retried = False
    async with websockets.connect(relay, open_timeout=timeout) as ws:
        req = json.dumps(["REQ", "q", filt])
        await ws.send(req)
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            except asyncio.TimeoutError:
                break
            kind = msg[0] if msg else ""
            if kind == "AUTH" and len(msg) > 1 and isinstance(msg[1], str):
                challenge = msg[1]
                authed = await _send_auth(ws, relay, challenge)
            elif kind == "EVENT" and len(msg) > 2 and msg[1] == "q":
                events.append(msg[2])
            elif kind == "EOSE":
                break
            elif kind == "CLOSED":
                reason = msg[2] if len(msg) > 2 else ""
                if "auth-required" in str(reason) and challenge and not retried:
                    retried = True
                    if not authed:
                        authed = await _send_auth(ws, relay, challenge)
                    if authed:
                        await ws.send(req)
                        continue
                print(f"relay closed subscription: {reason}", file=sys.stderr)
                break
            elif kind == "NOTICE":
                print(f"NOTICE: {msg[1] if len(msg) > 1 else ''}", file=sys.stderr)
            elif kind == "OK":
                continue
    return events


async def publish(relay, event_json, timeout=15):
    import websockets

    event = json.loads(event_json)
    if not _check(event):
        raise SystemExit("refusing to publish an event that fails id/signature verification")
    challenge = None
    sent_auth = False
    resent = False
    async with websockets.connect(relay, open_timeout=timeout) as ws:
        payload = json.dumps(["EVENT", event])
        await ws.send(payload)
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            kind = msg[0] if msg else ""
            if kind == "AUTH" and len(msg) > 1 and isinstance(msg[1], str):
                challenge = msg[1]
                sent_auth = await _send_auth(ws, relay, challenge)
            elif kind == "OK":
                accepted = bool(msg[2]) if len(msg) > 2 else False
                reason = msg[3] if len(msg) > 3 else ""
                if (not accepted) and "auth-required" in str(reason) and challenge and not resent:
                    resent = True
                    if not sent_auth:
                        sent_auth = await _send_auth(ws, relay, challenge)
                    if sent_auth:
                        await ws.send(payload)
                        continue
                return msg
            elif kind == "NOTICE":
                print(f"NOTICE: {msg[1] if len(msg) > 1 else ''}", file=sys.stderr)


def info(relay, timeout=15):
    http = relay.replace("wss://", "https://").replace("ws://", "http://")
    req = urllib.request.Request(
        http,
        headers={"Accept": "application/nostr+json", "User-Agent": "nostr-skill"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def selfcheck():
    nk = _nostr_key()
    sk, _pk = nk.generate_keypair()
    os.environ["NOSTR_SECRET_KEY"] = sk
    ev = _auth_event("wss://relay.example.com", "challenge")
    ok = (
        ev["kind"] == 22242
        and ["challenge", "challenge"] in ev["tags"]
        and ["relay", "wss://relay.example.com"] in ev["tags"]
        and nk.verify_event(ev)
    )
    print("PASS auth-event" if ok else "FAIL auth-event")
    return ok


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "selfcheck":
        sys.exit(0 if selfcheck() else 1)
    if cmd == "query":
        events = asyncio.run(query(sys.argv[2], sys.argv[3]))
        bad = 0
        for ev in events:
            if not _check(ev):
                bad += 1
                print(f"INVALID id/sig {ev.get('id', '')}", file=sys.stderr)
            print(json.dumps(ev, ensure_ascii=False))
        print(f"# {len(events)} events, {bad} invalid", file=sys.stderr)
        sys.exit(2 if bad else 0)
    if cmd == "publish":
        raw = sys.stdin.read() if len(sys.argv) < 4 or sys.argv[3] == "-" else sys.argv[3]
        res = asyncio.run(publish(sys.argv[2], raw))
        ok = bool(res[2]) if len(res) > 2 else False
        print(f"{'ACCEPTED' if ok else 'REJECTED'}: {res[3] if len(res) > 3 else ''}")
        sys.exit(0 if ok else 1)
    if cmd == "info":
        print(json.dumps(info(sys.argv[2]), indent=2, ensure_ascii=False))
        return
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
