#!/usr/bin/env python3
"""Small Nostr relay inspector.

Query results include explicit completeness metadata. An EOSE without NIP-67's
"finish" hint is not reported as complete. This client does not paginate a
NIP-67 "more" response; it labels the result as incomplete instead.
"""
from __future__ import annotations
import asyncio
import json
import sys
from urllib.parse import urlsplit
import urllib.request

import websockets

async def query(relay: str, filter_json: str, timeout: float = 15.0) -> dict:
    filt = json.loads(filter_json)
    events: list[dict] = []
    result = {
        "relay": relay,
        "events": events,
        "eose": False,
        "eose_hints": [],
        "completeness": "unknown",
        "complete": False,
        "error": None,
    }
    try:
        async with websockets.connect(relay, open_timeout=timeout, close_timeout=2) as ws:
            await ws.send(json.dumps(["REQ", "q", filt]))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    result["completeness"] = "timeout"
                    result["error"] = "timed out before EOSE"
                    break
                try:
                    msg = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(msg, list) or not msg:
                    continue
                if msg[0] == "EVENT" and len(msg) >= 3 and msg[1] == "q":
                    events.append(msg[2])
                elif msg[0] == "EOSE" and len(msg) >= 2 and msg[1] == "q":
                    result["eose"] = True
                    hints = msg[2] if len(msg) > 2 and isinstance(msg[2], list) else []
                    result["eose_hints"] = [str(hint) for hint in hints]
                    if "auth" in hints:
                        result["completeness"] = "auth-required"
                        result["error"] = "relay indicates additional results may require NIP-42 AUTH"
                    elif "more" in hints:
                        result["completeness"] = "more-available"
                        result["error"] = "relay indicates additional stored events; pagination is not implemented"
                    elif "finish" in hints:
                        result["completeness"] = "complete"
                        result["complete"] = True
                    else:
                        result["completeness"] = "unknown"
                        result["error"] = "EOSE received without a definitive NIP-67 finish hint"
                    break
                elif msg[0] == "CLOSED":
                    result["completeness"] = "closed"
                    result["error"] = str(msg[2] if len(msg) > 2 else "subscription closed")[:240]
                    break
                elif msg[0] == "NOTICE":
                    result["error"] = str(msg[1] if len(msg) > 1 else "relay notice")[:240]
    except Exception as exc:
        result["completeness"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"[:240]
    result["event_count"] = len(events)
    return result

async def publish(relay: str, event_json: str, timeout: float = 15.0) -> dict:
    event = json.loads(event_json)
    async with websockets.connect(relay, open_timeout=timeout, close_timeout=2) as ws:
        await ws.send(json.dumps(["EVENT", event]))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if isinstance(msg, list) and len(msg) >= 3 and msg[0] == "OK" and msg[1] == event.get("id"):
                return {"accepted": bool(msg[2]), "message": str(msg[3] if len(msg) > 3 else "")[:240]}
            if isinstance(msg, list) and msg and msg[0] == "NOTICE":
                continue

def info(relay: str, timeout: float = 15.0) -> dict:
    parts = urlsplit(relay)
    if parts.scheme not in ("ws", "wss") or not parts.netloc:
        raise ValueError("relay must be a ws:// or wss:// URL")
    scheme = "https" if parts.scheme == "wss" else "http"
    url = scheme + "://" + parts.netloc + parts.path
    req = urllib.request.Request(url, headers={"Accept": "application/nostr+json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    try:
        if cmd == "query" and len(sys.argv) >= 4:
            result = asyncio.run(query(sys.argv[2], sys.argv[3]))
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["eose"] and result["complete"] else 1
        if cmd == "publish" and len(sys.argv) >= 4:
            event_json = sys.argv[3]
            if event_json == "-":
                event_json = sys.stdin.read()
            result = asyncio.run(publish(sys.argv[2], event_json))
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["accepted"] else 1
        if cmd == "info" and len(sys.argv) >= 3:
            print(json.dumps(info(sys.argv[2]), indent=2, ensure_ascii=False))
            return 0
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(__doc__)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
