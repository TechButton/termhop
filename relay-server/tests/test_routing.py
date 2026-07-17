# termhop relay tests — full pair_init -> pair_request -> pair_challenge x2 ->
# pair_complete -> session_open -> pty_data/pty_input -> session_close round
# trip, against a real running relay instance (see conftest.relay_server_url).
import pytest

from tests.fake_peer import FakePeer

pytestmark = pytest.mark.asyncio


async def test_full_pairing_and_data_round_trip(relay_server_url):
    agent = await FakePeer.connect(relay_server_url, "agent")
    client = await FakePeer.connect(relay_server_url, "client")

    session_id = "sess-abc123"
    token = "tok_" + "e" * 16

    await agent.send("pair_init", payload={"token": token, "agent_pubkey": "AGENT_PUB", "session_id": session_id})
    ack = await agent.recv()
    assert ack["type"] == "pair_init_ack"

    await client.send("pair_request", payload={"token": token, "client_pubkey": "CLIENT_PUB"})

    client_challenge = await client.recv()
    assert client_challenge["type"] == "pair_challenge"
    assert client_challenge["session_id"] == session_id
    assert client_challenge["payload"]["peer_pubkey"] == "AGENT_PUB"

    agent_challenge = await agent.recv()
    assert agent_challenge["type"] == "pair_challenge"
    assert agent_challenge["session_id"] == session_id
    assert agent_challenge["payload"]["peer_pubkey"] == "CLIENT_PUB"

    await agent.send("pair_complete", session_id=session_id)
    await client.send("pair_complete", session_id=session_id)

    # canary marker stands in for real ciphertext — relay must never inspect it
    canary = "CANARY-PTY-DATA-MARKER"
    await client.send("pty_input", session_id=session_id, payload={"nonce": "n1", "ciphertext": canary})
    agent_side = await agent.recv()
    assert agent_side["type"] == "pty_input"
    assert agent_side["payload"]["ciphertext"] == canary

    await agent.send("pty_data", session_id=session_id, payload={"nonce": "n2", "ciphertext": "OUTPUT-CANARY"})
    client_side = await client.recv()
    assert client_side["type"] == "pty_data"
    assert client_side["payload"]["ciphertext"] == "OUTPUT-CANARY"

    await client.send("session_close", session_id=session_id, payload={})
    agent_close = await agent.recv()
    assert agent_close["type"] == "session_close"

    await agent.close()
    await client.close()


async def test_second_pair_request_with_same_token_rejected(relay_server_url):
    agent = await FakePeer.connect(relay_server_url, "agent")
    client1 = await FakePeer.connect(relay_server_url, "client")
    client2 = await FakePeer.connect(relay_server_url, "client")

    token = "tok_" + "f" * 16
    await agent.send("pair_init", payload={"token": token, "agent_pubkey": "AP", "session_id": "sess-dup"})
    await agent.recv()  # pair_init_ack
    await client1.send("pair_request", payload={"token": token, "client_pubkey": "CP1"})
    await client1.recv()  # pair_challenge
    await agent.recv()  # pair_challenge

    await client2.send("pair_request", payload={"token": token, "client_pubkey": "CP2"})
    err = await client2.recv()
    assert err["type"] == "error"
    assert err["payload"]["code"] == "token_invalid"

    await agent.close()
    await client1.close()
    await client2.close()


async def test_pair_request_unknown_token_rejected(relay_server_url):
    client = await FakePeer.connect(relay_server_url, "client")
    await client.send("pair_request", payload={"token": "tok_" + "z" * 16, "client_pubkey": "CP"})
    err = await client.recv()
    assert err["type"] == "error"
    assert err["payload"]["code"] == "token_invalid"
    await client.close()
