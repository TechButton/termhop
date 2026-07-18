# termhop relay tests — session_list/session_open/session_resize/idle_alert
# plaintext metadata pass-through (relay routes without inspecting payload).
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


async def test_session_list_routes_agent_to_client(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-list", "tok_" + "g" * 16)

    sessions = [{"pid": 123, "cwd": "/home/user/project", "cmd": "bash", "status": "running", "last_output_ts": 1}]
    await agent.send("session_list", session_id="sess-list", payload={"sessions": sessions})
    received = await client.recv()
    assert received["type"] == "session_list"
    assert received["payload"]["sessions"] == sessions

    await agent.close()
    await client.close()


async def test_session_open_routes_client_to_agent(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-open", "tok_" + "h" * 16)

    await client.send("session_open", session_id="sess-open", payload={"pid": 456})
    received = await agent.recv()
    assert received["type"] == "session_open"
    assert received["payload"]["pid"] == 456

    await agent.close()
    await client.close()


async def test_session_resize_routes_client_to_agent(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-resize", "tok_" + "i" * 16)

    await client.send("session_resize", session_id="sess-resize", payload={"rows": 40, "cols": 120})
    received = await agent.recv()
    assert received["type"] == "session_resize"
    assert received["payload"] == {"rows": 40, "cols": 120}

    await agent.close()
    await client.close()


async def test_idle_alert_routes_agent_to_client(relay_server_url):
    agent, client = await _paired_session(relay_server_url, "sess-idle", "tok_" + "j" * 16)

    await agent.send("idle_alert", session_id="sess-idle", payload={"reason": "waiting_for_input"})
    received = await client.recv()
    assert received["type"] == "idle_alert"
    assert received["payload"]["reason"] == "waiting_for_input"

    await agent.close()
    await client.close()
