# termhop agent tests — RelayClient's handshake driven against a REAL
# relay-server instance, with a FakeClientPeer playing the client role and
# doing independent ECDH math, proving actual interop.
import asyncio

import pytest
import websockets

from common.relay_client import HandshakeError, RelayClient
from tests.fake_client_peer import FakeClientPeer

pytestmark = pytest.mark.asyncio


async def test_remote_plaintext_relay_url_is_rejected():
    with pytest.raises(HandshakeError, match="loopback"):
        RelayClient("ws://relay.example.com")


async def test_full_handshake_and_encrypted_round_trip(relay_server_url):
    agent = RelayClient(relay_server_url, agent_hostname="test-box.local")

    await agent.connect()
    token, session_id = await agent.send_pair_init()
    await agent.await_pair_init_ack()
    assert agent.pairing_secret is not None
    assert agent.agent_pubkey_b64 is not None

    client = await FakeClientPeer.connect(relay_server_url)
    client_pair = asyncio.create_task(
        client.pair_request_and_complete(
            token, agent.pairing_secret, agent.agent_pubkey_b64, session_id
        )
    )
    await agent.await_pair_challenge_and_complete()
    hostname = await client_pair
    assert hostname == "test-box.local"

    assert agent.session_keys == client.session_keys
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


async def test_saved_device_resume_derives_fresh_matching_keys(relay_server_url):
    from common import pairing

    device_id = pairing.generate_device_id()
    device_secret = pairing.generate_pairing_secret()
    agent = RelayClient(relay_server_url, agent_hostname="rebooted-box")
    await agent.connect()
    await agent.send_resume_init(device_id=device_id, device_secret=device_secret)

    client = await FakeClientPeer.connect(relay_server_url)
    client_resume = asyncio.create_task(
        client.resume_request_and_complete(device_id, device_secret)
    )
    await agent.await_resume_and_complete()
    assert await client_resume == "rebooted-box"
    assert agent.session_keys == client.session_keys

    await agent.send_pty_data(b"fresh session")
    assert client.decrypt(await client.recv()) == b"fresh session"
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
            {
                "v": 2,
                "type": "pair_challenge",
                "session_id": session_id,
                "seq": 2,
                "ts": 1,
                "payload": {},
            }
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
            v=2,
            type="pair_init",
            session_id=None,
            seq=1,
            ts=int(time.time() * 1000),
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


async def test_agent_rejects_client_without_out_of_band_secret(relay_server_url):
    import time

    from common import crypto
    from common.envelope import Envelope

    agent = RelayClient(relay_server_url)
    await agent.connect()
    token, _ = await agent.send_pair_init()
    await agent.await_pair_init_ack()

    raw_client = await websockets.connect(f"{relay_server_url}/ws/client")
    _, client_pub = crypto.generate_ephemeral_keypair()
    request = Envelope(
        v=2,
        type="pair_request",
        session_id=None,
        seq=1,
        ts=int(time.time() * 1000),
        payload={
            "token": token,
            "client_pubkey": crypto.encode_pubkey(client_pub),
            # Structurally valid 32-byte proof, but deliberately not derived
            # from the out-of-band pairing secret.
            "client_proof": "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI=",
        },
    )
    await raw_client.send(request.model_dump_json())
    await raw_client.recv()  # client-side pair_challenge

    with pytest.raises(HandshakeError, match="client pairing proof is invalid"):
        await agent.await_pair_challenge_and_complete()

    await raw_client.close()
    await agent.close()
