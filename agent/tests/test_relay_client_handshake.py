# termhop agent tests — RelayClient's handshake driven against a REAL
# relay-server instance, with a FakeClientPeer playing the client role and
# doing independent ECDH math, proving actual interop.
import pytest
import websockets

from common.relay_client import HandshakeError, RelayClient
from tests.fake_client_peer import FakeClientPeer

pytestmark = pytest.mark.asyncio


async def test_full_handshake_and_encrypted_round_trip(relay_server_url):
    agent = RelayClient(relay_server_url, agent_hostname="test-box.local")

    await agent.connect()
    token, session_id = await agent.send_pair_init()
    await agent.await_pair_init_ack()

    client = await FakeClientPeer.connect(relay_server_url)
    hostname = await client.pair_request_and_complete(token)
    assert hostname == "test-box.local"

    await agent.await_pair_challenge_and_complete()

    assert agent.session_key == client.session_key
    assert agent.session_id == session_id == client.session_id

    canary = b"CANARY-HANDSHAKE-INTEROP-MARKER"
    await agent.send_pty_data(canary)
    data_envelope = await client.recv()
    assert data_envelope.type == "pty_data"
    assert client.decrypt(data_envelope) == canary

    await client.send_encrypted("pty_input", b"echo hi\n")
    input_envelope = await agent.recv_decrypted()
    assert input_envelope.type == "pty_input"
    assert agent.decrypt_payload(input_envelope) == b"echo hi\n"

    await agent.close()
    await client.close()


async def test_malformed_pair_challenge_missing_peer_pubkey_raises(relay_server_url):
    agent = RelayClient(relay_server_url)
    await agent.connect()
    token, session_id = await agent.send_pair_init()
    await agent.await_pair_init_ack()

    # Simulate a broken/malicious relay sending a pair_challenge without
    # peer_pubkey by talking to the raw agent-role socket directly.
    import json

    await agent._ws.send(  # noqa: SLF001 — deliberately reaching into internals to inject a bad message for this test
        json.dumps(
            {"v": 1, "type": "pair_challenge", "session_id": session_id, "seq": 1, "ts": 1, "payload": {}}
        )
    )

    with pytest.raises(HandshakeError):
        await agent.await_pair_challenge_and_complete()

    await agent.close()


async def test_relay_error_envelope_during_pairing_raises(relay_server_url):
    agent = RelayClient(relay_server_url)
    await agent.connect()

    # Unknown token format triggers the relay's own validation error path.
    agent.token = "bad"
    agent.session_id = "sess-x"
    import time

    from common.envelope import Envelope

    await agent._ws.send(  # noqa: SLF001
        Envelope(
            v=1, type="pair_init", session_id=None, seq=1, ts=int(time.time() * 1000),
            payload={"token": "short", "agent_pubkey": "x", "session_id": "sess-x"},
        ).model_dump_json()
    )
    with pytest.raises(HandshakeError):
        await agent.await_pair_init_ack()

    await agent.close()


async def test_ws_disconnect_mid_handshake_raises(relay_server_url):
    agent = RelayClient(relay_server_url)
    await agent.connect()
    await agent.send_pair_init()
    await agent.close()

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await agent.await_pair_init_ack()
