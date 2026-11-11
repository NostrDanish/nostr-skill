import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "nostr_key.py"
spec = importlib.util.spec_from_file_location("nostr_key", SCRIPT)
nostr_key = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = nostr_key
spec.loader.exec_module(nostr_key)

class PublicNip19Tests(unittest.TestCase):
    def test_npub_round_trip(self):
        public_key = "ab" * 32
        encoded = nostr_key.encode_entity("npub", public_key)
        self.assertEqual(nostr_key.decode_entity(encoded), {"type": "npub", "hex": public_key})

    def test_note_round_trip(self):
        event_id = "cd" * 32
        encoded = nostr_key.encode_entity("note", event_id)
        self.assertEqual(nostr_key.decode_entity(encoded), {"type": "note", "hex": event_id})

    def test_nprofile_round_trip(self):
        public_key = "12" * 32
        encoded = nostr_key.encode_entity("nprofile", public_key, ["wss://relay.example"])
        decoded = nostr_key.decode_entity(encoded)
        self.assertEqual(decoded["pubkey"], public_key)
        self.assertEqual(decoded["relays"], ["wss://relay.example"])

    def test_nevent_round_trip(self):
        event_id = "34" * 32
        author = "56" * 32
        encoded = nostr_key.encode_entity("nevent", event_id, ["wss://relay.example"], author, 1)
        decoded = nostr_key.decode_entity(encoded)
        self.assertEqual(decoded["event_id"], event_id)
        self.assertEqual(decoded["author"], author)
        self.assertEqual(decoded["kind"], 1)

    def test_naddr_round_trip(self):
        author = "78" * 32
        encoded = nostr_key.encode_entity("naddr", "article-id", ["wss://relay.example"], author, 30023)
        decoded = nostr_key.decode_entity(encoded)
        self.assertEqual(decoded["identifier"], "article-id")
        self.assertEqual(decoded["pubkey"], author)
        self.assertEqual(decoded["kind"], 30023)

    def test_nsec_is_never_decoded(self):
        encoded = nostr_key.bech32_encode("nsec", bytes.fromhex("01" * 32))
        with self.assertRaisesRegex(ValueError, "intentionally disabled"):
            nostr_key.decode_entity(encoded)

    def test_private_entity_cannot_be_encoded(self):
        with self.assertRaisesRegex(ValueError, "nsec is prohibited"):
            nostr_key.encode_entity("nsec", "01" * 32)

    def test_invalid_public_key_length_rejected(self):
        with self.assertRaisesRegex(ValueError, "64 hexadecimal"):
            nostr_key.encode_entity("npub", "abcd")

    def test_malformed_tlv_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncated TLV"):
            nostr_key._tlv_decode(bytes([0, 3, 1]))

if __name__ == "__main__":
    unittest.main()
