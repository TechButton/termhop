# termhop relay tests — port_forward_request/data/close routing. The relay
# has no visibility into *which* forwarded port a given port_forward_data
# belongs to once it's routing ciphertext — per-port lifecycle enforcement
# (e.g. rejecting data after a specific port's close) is the agent/client's
# job, not the relay's; the relay only ever routes by session_id.
import pytest

from tests.fake_peer import FakePeer

pytestmark = pytest.mark.asyncio


async def _paired_session(relay_server_url, session_id: str, token: str) -> tuple[FakePeer, FakePeer]:
    agent = await FakePeer.connect(relay_server_url, "agent")
    client = await FakePeer.connect(relay_server_url, "client")

    await agent.send("pair_init", payload={"token": token, "agent_pubkey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "session_id": session_id})
    await agent.recv()  # pair_init_ack

    await client.send(
        "pair_request", payload={"token": token, "client_pubkey": "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=", "client_proof": "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI="}
    )
    await client.recv()  # pair_challenge
    await agent.recv()  # pair_challenge

    await agent.send("pair_complete", session_id=session_id, payload={"agent_proof": "AwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwM="})
    await client.recv()  # pair_complete
    return agent, client


async def test_port_forward_request_routes_client_to_agent(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-pf-req", "tok_" + "k" * 16)

    await client.send("port_forward_request", session_id="sess-pf-req", payload={"port": 3000})
    received = await agent.recv()
    assert received["type"] == "port_forward_request"
    assert received["payload"]["port"] == 3000

    await agent.close()
    await client.close()


async def test_port_forward_data_routes_bidirectionally(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-pf-data", "tok_" + "l" * 16)

    await agent.send(
        "port_forward_data", session_id="sess-pf-data", payload={"nonce": "n", "ciphertext": "AGENT-TO-CLIENT"}
    )
    to_client = await client.recv()
    assert to_client["type"] == "port_forward_data"
    assert to_client["payload"]["ciphertext"] == "AGENT-TO-CLIENT"

    await client.send(
        "port_forward_data", session_id="sess-pf-data", payload={"nonce": "n", "ciphertext": "CLIENT-TO-AGENT"}
    )
    to_agent = await agent.recv()
    assert to_agent["type"] == "port_forward_data"
    assert to_agent["payload"]["ciphertext"] == "CLIENT-TO-AGENT"

    await agent.close()
    await client.close()


async def test_port_forward_close_routes_and_session_stays_open(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-pf-close", "tok_" + "m" * 16)

    await client.send("port_forward_close", session_id="sess-pf-close", payload={"port": 3000})
    received = await agent.recv()
    assert received["type"] == "port_forward_close"

    # session itself is untouched by a port-level close — pty traffic still routes
    await agent.send("pty_data", session_id="sess-pf-close", payload={"nonce": "n", "ciphertext": "STILL-ALIVE"})
    still_alive = await client.recv()
    assert still_alive["payload"]["ciphertext"] == "STILL-ALIVE"

    await agent.close()
    await client.close()
