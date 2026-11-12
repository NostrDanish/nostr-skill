import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "nostr_query.py"
spec = importlib.util.spec_from_file_location("nostr_query", SCRIPT)
nostr_query = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = nostr_query
spec.loader.exec_module(nostr_query)

class FakeWebSocket:
    def __init__(self, pages):
        self.pages = pages
        self.sent = []
        self.current = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, raw):
        request = json.loads(raw)
        if request[0] == "REQ":
            self.sent.append(request)
            self.current = list(self.pages[len(self.sent) - 1])

    async def recv(self):
        if not self.current:
            raise asyncio.TimeoutError()
        return json.dumps(self.current.pop(0))

class NostrQueryCompletenessTests(unittest.TestCase):
    def test_more_is_paginated_until_finish(self):
        first = {"id": "event-1", "created_at": 100}
        second = {"id": "event-2", "created_at": 90}
        ws = FakeWebSocket([
            [["EVENT", "q-0", first], ["EOSE", "q-0", ["more"]]],
            [["EVENT", "q-1", second], ["EOSE", "q-1", ["finish"]]],
        ])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", '{"kinds":[1]}'))
        self.assertTrue(result["complete"])
        self.assertEqual(result["completeness"], "complete")
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(ws.sent[1][2]["until"], 100)

    def test_auth_hint_precedes_finish(self):
        ws = FakeWebSocket([[["EOSE", "q-0", ["auth", "finish"]]]])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", "{}"))
        self.assertFalse(result["complete"])
        self.assertEqual(result["completeness"], "auth-required")

    def test_plain_eose_is_unknown(self):
        ws = FakeWebSocket([[["EOSE", "q-0"]]])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", "{}"))
        self.assertFalse(result["complete"])
        self.assertEqual(result["completeness"], "unknown")

    def test_plain_and_unknown_hints_use_legacy_pagination(self):
        first = {"id": "event-1", "created_at": 100}
        second = {"id": "event-2", "created_at": 90}
        ws = FakeWebSocket([
            [["EVENT", "q-0", first], ["EOSE", "q-0"]],
            [["EVENT", "q-1", second], ["EOSE", "q-1", ["future-hint"]]],
            [["EOSE", "q-2"]],
        ])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", '{"kinds":[1]}'))
        self.assertFalse(result["complete"])
        self.assertFalse(result["partial"])
        self.assertEqual(result["completeness"], "unknown")
        self.assertEqual(result["pages"], 3)
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(ws.sent[1][2]["until"], 100)
        self.assertEqual(ws.sent[2][2]["until"], 90)

    def test_duplicate_only_more_page_stops_partial(self):
        event = {"id": "same-event", "created_at": 100}
        ws = FakeWebSocket([
            [["EVENT", "q-0", event], ["EOSE", "q-0", ["more"]]],
            [["EVENT", "q-1", event], ["EOSE", "q-1", ["more"]]],
        ])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", "{}"))
        self.assertEqual(result["completeness"], "partial")
        self.assertEqual(result["event_count"], 1)
        self.assertFalse(result["complete"])

    def test_pagination_limit_is_reported(self):
        event = {"id": "event-1", "created_at": 100}
        ws = FakeWebSocket([[["EVENT", "q-0", event], ["EOSE", "q-0", ["more"]]]])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", "{}", max_pages=1))
        self.assertEqual(result["completeness"], "pagination-limit")
        self.assertFalse(result["complete"])

    def test_timeout_before_eose_is_partial(self):
        event = {"id": "event-1", "created_at": 100}
        ws = FakeWebSocket([[["EVENT", "q-0", event]]])
        with patch.object(nostr_query.websockets, "connect", return_value=ws):
            result = asyncio.run(nostr_query.query("wss://relay.example", "{}", timeout=0.01))
        self.assertEqual(result["completeness"], "timeout")
        self.assertTrue(result["partial"])
        self.assertFalse(result["complete"])



    def setUp(self):
        self.dns_patch = patch.object(
            nostr_query.socket,
            "getaddrinfo",
            return_value=[
                (nostr_query.socket.AF_INET, nostr_query.socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
            ],
        )
        self.dns_patch.start()
        self.addCleanup(self.dns_patch.stop)

    def test_websocket_connect_is_dns_pinned_and_proxy_disabled(self):
        ws = FakeWebSocket([[["EOSE", "q-0", ["finish"]]]])
        with patch.object(nostr_query.websockets, "connect", return_value=ws) as connect:
            result = asyncio.run(nostr_query.query("wss://relay.example", "{}"))
        self.assertTrue(result["complete"])
        self.assertEqual(connect.call_args.kwargs["host"], "8.8.8.8")
        self.assertEqual(connect.call_args.kwargs["port"], 443)
        self.assertIsNone(connect.call_args.kwargs["proxy"])

    def test_websocket_rejects_loopback_and_private_dns(self):
        with self.assertRaisesRegex(ValueError, "non-public"):
            nostr_query._relay_connect("wss://127.0.0.1", 1)
        self.dns_patch.stop()
        with patch.object(
            nostr_query.socket,
            "getaddrinfo",
            return_value=[
                (nostr_query.socket.AF_INET, nostr_query.socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                (nostr_query.socket.AF_INET, nostr_query.socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443)),
            ],
        ):
            with self.assertRaisesRegex(ValueError, "non-public"):
                nostr_query._relay_connect("wss://rebind.example", 1)

    def test_nip11_rejects_private_endpoint_before_connecting(self):
        with self.assertRaisesRegex(ValueError, "non-public"):
            nostr_query.info("wss://127.0.0.1")


if __name__ == "__main__":
    unittest.main()
