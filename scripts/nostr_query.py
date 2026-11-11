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

def classify_eose_hints(hints: list[str]) -> tuple[str, str | None]:
    """Classify NIP-67 EOSE hints. AUTH takes precedence over finish."""
    if "auth" in hints:
        return "auth-required", "relay indicates additional results may require NIP-42 AUTH"
    if "more" in hints:
        return "more-available", None
    if "finish" in hints:
        return "complete", None
    return "unknown", "EOSE received without a definitive NIP-67 finish hint"


async def query(relay: str, filter_json: str, timeout: float = 15.0, max_pages: int = 10) -> dict:
    base_filter = json.loads(filter_json)
    if not isinstance(base_filter, dict):
        raise ValueError("NIP-01 filter must be a JSON object")
    if not 1 <= max_pages <= 50:
        raise ValueError("max_pages must be between 1 and 50")

    events: list[dict] = []
    seen_ids: set[str] = set()
    result = {
        "relay": relay, "events": events, "eose": False, "eose_hints": [],
        "completeness": "unknown", "complete": False, "partial": False,
        "pages": 0, "event_count": 0, "error": None,
    }
    current_filter = dict(base_filter)

    try:
        async with websockets.connect(relay, open_timeout=timeout, close_timeout=2) as ws:
            for page_index in range(max_pages):
                sub_id = f"q-{page_index}"
                await ws.send(json.dumps(["REQ", sub_id, current_filter]))
                page_events: list[dict] = []
                fresh_count = 0
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        result["completeness"] = "timeout"
                        result["partial"] = True
                        result["error"] = "timed out before EOSE"
                        break
                    try:
                        msg = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    if not isinstance(msg, list) or not msg:
                        continue
                    if msg[0] == "EVENT" and len(msg) >= 3 and msg[1] == sub_id:
                        event = msg[2]
                        if not isinstance(event, dict) or not isinstance(event.get("id"), str):
                            continue
                        page_events.append(event)
                        if event["id"] not in seen_ids:
                            seen_ids.add(event["id"])
                            events.append(event)
                            fresh_count += 1
                    elif msg[0] == "EOSE" and len(msg) >= 2 and msg[1] == sub_id:
                        result["eose"] = True
                        hints = msg[2] if len(msg) > 2 and isinstance(msg[2], list) else []
                        result["eose_hints"] = [str(hint) for hint in hints]
                        state, hint_error = classify_eose_hints(result["eose_hints"])
                        if state == "complete":
                            result["completeness"] = "complete"
                        elif state == "unknown":
                            result["completeness"] = "unknown"
                            result["error"] = hint_error
                        elif state == "auth-required":
                            result["completeness"] = "auth-required"
                            result["partial"] = True
                            result["error"] = hint_error
                        else:
                            if page_index + 1 >= max_pages:
                                result["completeness"] = "pagination-limit"
                                result["partial"] = True
                                result["error"] = f"pagination stopped at the {max_pages}-page safety limit"
                            elif fresh_count == 0 or not page_events:
                                result["completeness"] = "partial"
                                result["partial"] = True
                                result["error"] = "NIP-67 more hint received but pagination made no progress"
                            else:
                                timestamps = [
                                    int(event["created_at"]) for event in page_events
                                    if isinstance(event.get("created_at"), int)
                                ]
                                if not timestamps:
                                    result["completeness"] = "partial"
                                    result["partial"] = True
                                    result["error"] = "NIP-67 more hint received but no created_at cursor was available"
                                else:
                                    oldest = min(timestamps)
                                    previous_until = current_filter.get("until")
                                    if previous_until is not None and oldest > int(previous_until):
                                        result["completeness"] = "partial"
                                        result["partial"] = True
                                        result["error"] = "pagination cursor did not move backward"
                                    else:
                                        current_filter = dict(base_filter)
                                        current_filter["until"] = oldest
                                        result["completeness"] = "more-available"
                        break
                    elif msg[0] == "CLOSED" and len(msg) >= 2 and msg[1] == sub_id:
                        result["completeness"] = "closed"
                        result["partial"] = True
                        result["error"] = str(msg[2] if len(msg) > 2 else "subscription closed")[:240]
                        break
                    elif msg[0] == "NOTICE":
                        result["error"] = str(msg[1] if len(msg) > 1 else "relay notice")[:240]

                result["pages"] = page_index + 1
                if result["completeness"] != "more-available":
                    break
    except Exception as exc:
        result["completeness"] = "error"
        result["partial"] = True
        result["error"] = f"{type(exc).__name__}: {exc}"[:240]

    result["event_count"] = len(events)
    result["complete"] = result["completeness"] == "complete"
    if result["complete"]:
        result["partial"] = False
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
