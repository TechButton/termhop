"""Relay protocol state and input-validation security tests."""

import base64
import unittest
from unittest.mock import AsyncMock, Mock

from relay.config import Config
from relay.envelope import Envelope, EnvelopeInvalid, parse_envelope
from relay.pairing import validate_token_format
from relay.ratelimit import ConnectionLimiter
from relay.router import ConnectionContext, dispatch, handle_routable
from relay.session_registry import SessionRegistry
from relay.ws_handlers import _client_ip


def config() -> Config:
    return Config(
        domain="relay.example.com",
        redis_url="redis://localhost/0",
        pairing_token_ttl_s=120,
        session_pending_ttl_s=60,
        max_envelope_bytes=262144,
        protocol_version=2,
        rate_limit_ip_max=20,
        rate_limit_ip_window_s=300,
        rate_limit_token_max=5,
        token_min_len=16,
        token_max_len=128,
        handshake_timeout_s=20,
        client_origins=("https://client.example.com",),
        release="test",
        trusted_proxy_ips=frozenset(),
        max_connections_per_ip=40,
    )


class RelaySecurityBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_traffic_is_blocked_before_authentication(self) -> None:
        agent = AsyncMock()
        client = AsyncMock()
        registry = SessionRegistry()
        slot = registry.attach("sess-test", "agent", agent)
        registry.attach("sess-test", "client", client)
        slot.phase = "pairing"
        ctx = ConnectionContext(
            ws=client,
            role="client",
            peer_ip="127.0.0.1",
            redis=AsyncMock(),
            cfg=config(),
            registry=registry,
            session_id="sess-test",
        )
        envelope = Envelope(
            v=2,
            type="pty_input",
            session_id="sess-test",
            seq=1,
            ts=1,
            payload={"ciphertext": base64.b64encode(b"x").decode()},
        )

        await handle_routable(ctx, envelope)

        agent.send_text.assert_not_awaited()
        client.send_text.assert_awaited_once()
        self.assertIn("handshake_incomplete", client.send_text.await_args.args[0])

    async def test_established_session_traffic_is_forwarded(self) -> None:
        agent = AsyncMock()
        client = AsyncMock()
        registry = SessionRegistry()
        slot = registry.attach("sess-test", "agent", agent)
        registry.attach("sess-test", "client", client)
        slot.phase = "established"
        ctx = ConnectionContext(
            ws=client,
            role="client",
            peer_ip="127.0.0.1",
            redis=AsyncMock(),
            cfg=config(),
            registry=registry,
            session_id="sess-test",
        )
        envelope = Envelope(
            v=2, type="pty_input", session_id="sess-test", seq=1, ts=1, payload={}
        )

        await handle_routable(ctx, envelope)

        agent.send_text.assert_awaited_once()
        client.send_text.assert_not_awaited()

    async def test_session_list_is_agent_only(self) -> None:
        client = AsyncMock()
        ctx = ConnectionContext(
            ws=client,
            role="client",
            peer_ip="127.0.0.1",
            redis=AsyncMock(),
            cfg=config(),
            registry=SessionRegistry(),
            session_id="sess-test",
        )
        envelope = Envelope(
            v=2, type="session_list", session_id="sess-test", seq=1, ts=1,
            payload={"sessions": [{"session_id": "sess-test", "label": "forged"}]},
        )

        await dispatch(ctx, envelope)

        client.send_text.assert_awaited_once()
        self.assertIn("not valid from the client role", client.send_text.await_args.args[0])

    def test_token_and_envelope_inputs_are_strict(self) -> None:
        with self.assertRaises(Exception):
            validate_token_format(123, config())  # type: ignore[arg-type]
        with self.assertRaises(EnvelopeInvalid):
            parse_envelope(
                '{"v":2,"type":"pty_data","seq":true,"ts":1,"payload":{}}',
                max_bytes=262144,
                expected_version=2,
            )


def _fake_websocket(peer_host: str, headers: dict[str, str]) -> Mock:
    ws = Mock()
    ws.client = Mock(host=peer_host)
    ws.headers = headers
    return ws


class ClientIpTests(unittest.TestCase):
    def test_untrusted_peer_cannot_spoof_forwarded_header(self) -> None:
        ws = _fake_websocket("203.0.113.9", {"x-forwarded-for": "10.0.0.1"})
        self.assertEqual(_client_ip(ws, frozenset()), "203.0.113.9")

    def test_trusted_proxy_forwarded_header_is_used(self) -> None:
        ws = _fake_websocket("172.18.0.1", {"x-forwarded-for": "203.0.113.9"})
        self.assertEqual(
            _client_ip(ws, frozenset({"172.18.0.1"})), "203.0.113.9"
        )

    def test_trusted_proxy_takes_last_hop_of_chain(self) -> None:
        ws = _fake_websocket(
            "172.18.0.1", {"x-forwarded-for": "10.0.0.5, 203.0.113.9"}
        )
        self.assertEqual(
            _client_ip(ws, frozenset({"172.18.0.1"})), "203.0.113.9"
        )

    def test_trusted_proxy_without_header_falls_back_to_peer(self) -> None:
        ws = _fake_websocket("172.18.0.1", {})
        self.assertEqual(_client_ip(ws, frozenset({"172.18.0.1"})), "172.18.0.1")


class ConnectionLimiterTests(unittest.TestCase):
    def test_blocks_once_per_ip_cap_is_reached(self) -> None:
        limiter = ConnectionLimiter()
        for _ in range(3):
            self.assertTrue(limiter.try_acquire("1.2.3.4", 3))
        self.assertFalse(limiter.try_acquire("1.2.3.4", 3))

    def test_other_ips_are_unaffected(self) -> None:
        limiter = ConnectionLimiter()
        for _ in range(3):
            limiter.try_acquire("1.2.3.4", 3)
        self.assertTrue(limiter.try_acquire("5.6.7.8", 3))

    def test_release_frees_a_slot(self) -> None:
        limiter = ConnectionLimiter()
        for _ in range(3):
            limiter.try_acquire("1.2.3.4", 3)
        limiter.release("1.2.3.4")
        self.assertTrue(limiter.try_acquire("1.2.3.4", 3))


if __name__ == "__main__":
    unittest.main()
