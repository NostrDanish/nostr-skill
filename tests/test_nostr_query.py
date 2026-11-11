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

if __name__ == "__main__":
    unittest.main()
