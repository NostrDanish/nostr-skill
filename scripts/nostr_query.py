#!/usr/bin/env python3
"""nostr_query.py — query and publish to Nostr relays over WebSocket.

Requires: pip install websockets

CLI:
  # Fetch events (filter is NIP-01 JSON). Prints one JSON event per line.
  python3 nostr_query.py query wss://relay.damus.io '{"kinds":[1],"limit":5}'
  python3 nostr_query.py query wss://relay.nostr.band '{"kinds":[0],"authors":["<hex-pubkey>"]}'

  # Fetch a NIP-11 relay information document.
  python3 nostr_query.py info wss://relay.damus.io

  # Publish a signed event (pipe from nostr_key.py sign).
  python3 nostr_query.py publish wss://relay.damus.io '<signed-event-json>'

Filter cheat sheet: kinds, ids, authors (prefixes allowed), #e/#p/#d/#t via
{"#e": [...]}, since/until (unix), limit, search (NIP-50, relay-dependent).
"""
import asyncio
import json
import sys
import urllib.request

import websockets


async def query(relay, filter_json, timeout=15):
    filt = json.loads(filter_json)
    events = []
    async with websockets.connect(relay, open_timeout=timeout) as ws:
        await ws.send(json.dumps(["REQ", "q", filt]))
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            except asyncio.TimeoutError:
                break
            if msg[0] == "EVENT" and msg[1] == "q":
                events.append(msg[2])
            elif msg[0] == "EOSE":
                break
            elif msg[0] == "CLOSED":
                print(f"relay closed subscription: {msg[2]}", file=sys.stderr)
                break
            elif msg[0] == "NOTICE":
                print(f"NOTICE: {msg[1]}", file=sys.stderr)
    return events


async def publish(relay, event_json, timeout=15):
    async with websockets.connect(relay, open_timeout=timeout) as ws:
        await ws.send(json.dumps(["EVENT", json.loads(event_json)]))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            if msg[0] == "OK":
                return msg  # ["OK", <event-id>, true|false, <message>]
            if msg[0] == "NOTICE":
                print(f"NOTICE: {msg[1]}", file=sys.stderr)


def info(relay, timeout=15):
    http = relay.replace("wss://", "https://").replace("ws://", "http://")
    req = urllib.request.Request(http, headers={"Accept": "application/nostr+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "query":
        events = asyncio.run(query(sys.argv[2], sys.argv[3]))
        for ev in events:
            print(json.dumps(ev, ensure_ascii=False))
        print(f"# {len(events)} events", file=sys.stderr)
    elif cmd == "publish":
        res = asyncio.run(publish(sys.argv[2], sys.argv[3]))
        ok = res[2]
        print(f"{'ACCEPTED' if ok else 'REJECTED'}: {res[3] if len(res) > 3 else ''}")
        sys.exit(0 if ok else 1)
    elif cmd == "info":
        doc = info(sys.argv[2])
        print(json.dumps(doc, indent=2, ensure_ascii=False))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
