#!/usr/bin/env python3
"""Nostr relay inspector with bounded NIP-67 completeness handling.

Query emits one JSON object containing events and completeness metadata.
Explicit NIP-67 "more" hints and legacy/unknown EOSE hints use bounded until
pagination (up to 10 pages by default). Only "finish" marks the result complete.
AUTH requirements, timeouts, CLOSED and pagination failures remain incomplete.
"""

from __future__ import annotations
import asyncio
import http.client
import ipaddress
import json
import socket
import ssl
import sys
from urllib.parse import urlsplit

import websockets



_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_MAX_INFO_BYTES = 1024 * 1024


def _resolve_public_target(url: str, allowed_schemes: set[str]):
    """Validate a network URL and resolve only globally routable destinations.

    The returned IPs must be used for the socket connection. Resolving here and
    letting a second resolver call happen later would reintroduce DNS rebinding.
    Every A/AAAA answer is checked; mixed public/private answers are rejected.
    """
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"invalid endpoint URL: {exc}") from exc

    if scheme not in allowed_schemes:
        raise ValueError(f"unsupported endpoint scheme: {scheme}")
    if not host:
        raise ValueError("endpoint URL has no hostname")
    if parts.username is not None or parts.password is not None:
        raise ValueError("credentials in endpoint URLs are not permitted")
    if parts.fragment:
        raise ValueError("endpoint URL fragments are not permitted")
    if "%" in host:
        raise ValueError("scoped IP literals are not permitted")

    default_port = 443 if scheme in ("https", "wss") else 80
    port = port if port is not None else default_port
    if not 1 <= port <= 65535:
        raise ValueError("endpoint port is out of range")

    try:
        literal = ipaddress.ip_address(host)
        ascii_host = str(literal)
        addresses = (literal,)
    except ValueError:
        try:
            ascii_host = host.encode("idna").decode("ascii")
            infos = socket.getaddrinfo(ascii_host, port, type=socket.SOCK_STREAM)
        except (UnicodeError, socket.gaierror, OSError) as exc:
            raise ValueError(f"DNS resolution failed for {host}: {exc}") from exc
        addresses = tuple(dict.fromkeys(
            ipaddress.ip_address(info[4][0].split("%", 1)[0])
            for info in infos
        ))

    if not addresses:
        raise ValueError(f"DNS returned no addresses for {host}")
    for address in addresses:
        if not address.is_global or address in _CGNAT:
            raise ValueError(f"endpoint resolves to non-public address {address}")
    return parts, ascii_host, port, tuple(str(address) for address in addresses)


def _relay_connect(relay: str, timeout: float):
    """Return a websockets connection pinned to a validated public IP.

    websockets keeps the URI hostname for TLS SNI/certificate verification and
    the Host header when host/port override only the TCP destination.
    Environment proxies are disabled so they cannot bypass this pin.
    """
    _parts, _host, port, addresses = _resolve_public_target(relay, {"ws", "wss"})
    return websockets.connect(
        relay,
        host=addresses[0],
        port=port,
        proxy=None,
        open_timeout=timeout,
        close_timeout=2,
    )


def _pinned_nip11_json(url: str, timeout: float) -> dict:
    """Fetch a NIP-11 document over a pinned socket; never follow redirects."""
    parts, host, port, addresses = _resolve_public_target(url, {"http", "https"})
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query

    host_header = f"[{host}]" if ":" in host else host
    default_port = 443 if parts.scheme.lower() == "https" else 80
    if port != default_port:
        host_header += f":{port}"

    last_error = None
    for address in addresses:
        raw_socket = None
        connection = None
        try:
            raw_socket = socket.create_connection((address, port), timeout=timeout)
            if parts.scheme.lower() == "https":
                raw_socket = ssl.create_default_context().wrap_socket(
                    raw_socket, server_hostname=host
                )
            connection = http.client.HTTPConnection(host, port, timeout=timeout)
            connection.sock = raw_socket
            raw_socket = None
            connection.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
            connection.putheader("Host", host_header)
            connection.putheader("Accept", "application/nostr+json")
            connection.putheader("Connection", "close")
            connection.endheaders()

            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise ValueError("NIP-11 redirects are not followed; validate the new URL separately")
            if response.status != 200:
                raise ValueError(f"NIP-11 endpoint returned HTTP {response.status}")
            length = response.getheader("Content-Length")
            if length is not None:
                try:
                    if int(length) > _MAX_INFO_BYTES:
                        raise ValueError("NIP-11 response exceeds 1 MiB")
                except ValueError as exc:
                    if "exceeds" in str(exc):
                        raise
                    raise ValueError("invalid NIP-11 Content-Length") from exc
            body = response.read(_MAX_INFO_BYTES + 1)
            if len(body) > _MAX_INFO_BYTES:
                raise ValueError("NIP-11 response exceeds 1 MiB")
            parsed = json.loads(body.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("NIP-11 response must be a JSON object")
            return parsed
        except OSError as exc:
            last_error = exc
        finally:
            if connection is not None:
                connection.close()
            elif raw_socket is not None:
                raw_socket.close()

    raise ValueError(f"couldn't connect to any validated NIP-11 address: {last_error}")


def classify_eose_hints(hints: list[str]) -> tuple[str, str | None]:
    """Classify NIP-67 hints; absent/unknown hints use legacy pagination."""
    if "auth" in hints:
        return "auth-required", "relay indicates additional results may require NIP-42 AUTH"
    if "more" in hints:
        return "more-available", None
    if "finish" in hints:
        return "complete", None
    # NIP-67 says unknown hints are ignored and their absence is not proof
    # of completion. Fall back to bounded legacy until-pagination.
    return "legacy", "no definitive NIP-67 hint; using bounded legacy pagination"


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
        async with _relay_connect(relay, timeout) as ws:
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
                        elif state == "auth-required":
                            result["completeness"] = "auth-required"
                            result["partial"] = True
                            result["error"] = hint_error
                        else:
                            legacy = state == "legacy"
                            if page_index + 1 >= max_pages:
                                result["completeness"] = "pagination-limit"
                                result["partial"] = True
                                result["error"] = f"pagination stopped at the {max_pages}-page safety limit"
                            elif fresh_count == 0 or not page_events:
                                result["completeness"] = "unknown" if legacy else "partial"
                                result["partial"] = not legacy
                                result["error"] = (
                                    "legacy pagination found no additional unique events; completeness remains unknown"
                                    if legacy else
                                    "NIP-67 more hint received but pagination made no progress"
                                )
                            else:
                                timestamps = [
                                    int(event["created_at"]) for event in page_events
                                    if isinstance(event.get("created_at"), int)
                                    and not isinstance(event.get("created_at"), bool)
                                    and event["created_at"] >= 0
                                ]
                                if not timestamps:
                                    result["completeness"] = "unknown" if legacy else "partial"
                                    result["partial"] = not legacy
                                    result["error"] = (
                                        "legacy pagination could not derive a created_at cursor"
                                        if legacy else
                                        "NIP-67 more hint received but no created_at cursor was available"
                                    )
                                else:
                                    oldest = min(timestamps)
                                    previous_until = current_filter.get("until")
                                    try:
                                        cursor_stalled = previous_until is not None and oldest >= int(previous_until)
                                    except (TypeError, ValueError):
                                        cursor_stalled = True
                                    if cursor_stalled:
                                        result["completeness"] = "unknown" if legacy else "partial"
                                        result["partial"] = not legacy
                                        result["error"] = "pagination cursor did not move backward"
                                    else:
                                        current_filter = dict(base_filter)
                                        current_filter["until"] = oldest
                                        result["completeness"] = "legacy-pagination" if legacy else "more-available"
                        break
                    elif msg[0] == "CLOSED" and len(msg) >= 2 and msg[1] == sub_id:
                        result["completeness"] = "closed"
                        result["partial"] = True
                        result["error"] = str(msg[2] if len(msg) > 2 else "subscription closed")[:240]
                        break
                    elif msg[0] == "NOTICE":
                        result["error"] = str(msg[1] if len(msg) > 1 else "relay notice")[:240]

                result["pages"] = page_index + 1
                if result["completeness"] in ("more-available", "legacy-pagination"):
                    # Close the previous live subscription before issuing the
                    # next bounded page so unrelated live events cannot starve it.
                    try:
                        await ws.send(json.dumps(["CLOSE", sub_id]))
                    except Exception:
                        pass
                    continue
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
    async with _relay_connect(relay, timeout) as ws:
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
    url = parts._replace(scheme=scheme).geturl()
    return _pinned_nip11_json(url, timeout)

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
