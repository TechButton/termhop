"""Security-boundary regression tests for local secrets and wire parsing."""

import base64
import os
import stat
import tempfile
import unittest
from pathlib import Path

from common.config import AgentConfig, load_config, save_config
from common.crypto import CryptoError, decode_pubkey, decrypt
from common.envelope import EnvelopeError, parse_envelope
from common.relay_client import HandshakeError, RelayClient


class AgentSecurityBoundaryTests(unittest.TestCase):
    def test_config_is_atomic_and_owner_only_on_posix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            save_config(
                AgentConfig(
                    relay_url="wss://relay.example.com",
                    device_id="dev-" + "a" * 32,
                    device_secret="secret",
                ),
                path,
            )
            self.assertEqual(load_config(path).device_id, "dev-" + "a" * 32)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(list(path.parent.glob(".config-*")), [])

    def test_relay_url_rejects_credentials_and_query(self) -> None:
        for value in (
            "wss://user:pass@relay.example.com",
            "wss://relay.example.com?redirect=bad",
            "wss://relay.example.com#fragment",
            "ws://relay.example.com",
        ):
            with self.subTest(value=value), self.assertRaises(HandshakeError):
                RelayClient(value)

    def test_envelope_rejects_coercion_and_extra_fields(self) -> None:
        with self.assertRaises(EnvelopeError):
            parse_envelope(
                '{"v":true,"type":"pty_data","seq":1,"ts":1,"payload":{}}'
            )
        with self.assertRaises(EnvelopeError):
            parse_envelope(
                '{"v":2,"type":"pty_data","seq":1,"ts":1,"payload":{},"extra":1}'
            )

    def test_crypto_rejects_wrong_sized_inputs_before_decryption(self) -> None:
        with self.assertRaises(CryptoError):
            decode_pubkey(base64.b64encode(b"short").decode())
        with self.assertRaises(CryptoError):
            decrypt(
                b"k" * 32,
                base64.b64encode(b"short").decode(),
                base64.b64encode(b"x" * 16).decode(),
                aad=b"aad",
            )


if __name__ == "__main__":
    unittest.main()
