"""Durable device routing remains opaque: relay validates shape/direction only."""

import pytest

from tests.fake_peer import FakePeer

pytestmark = pytest.mark.asyncio
KEY_A = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
KEY_B = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
PROOF_A = "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI="
PROOF_B = "AwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwM="


async def test_saved_device_reconnect_routes_proofs(relay_server_url):
    agent = await FakePeer.connect(relay_server_url, "agent")
    client = await FakePeer.connect(relay_server_url, "client")
    session_id = "sess-resumed1"
    device_id = "dev-0123456789abcdef0123456789abcdef"

    await agent.send(
        "resume_init",
        payload={
            "device_id": device_id,
            "session_id": session_id,
            "agent_pubkey": KEY_A,
            "agent_hostname": "workstation",
        },
    )
    assert (await agent.recv())["type"] == "resume_init_ack"

    await client.send("resume_request", payload={"device_id": device_id})
    assert (await agent.recv())["type"] == "resume_request"
    await agent.send(
        "resume_challenge",
        session_id=session_id,
        payload={
            "agent_pubkey": KEY_A,
            "agent_hostname": "workstation",
        },
    )
    assert (await client.recv())["type"] == "resume_challenge"

    await client.send(
        "resume_proof",
        session_id=session_id,
        payload={
            "client_pubkey": KEY_B,
            "client_proof": PROOF_A,
        },
    )
    assert (await agent.recv())["payload"]["client_proof"] == PROOF_A
    await agent.send(
        "resume_complete", session_id=session_id, payload={"agent_proof": PROOF_B}
    )
    assert (await client.recv())["payload"]["agent_proof"] == PROOF_B

    await agent.close()
    await client.close()


async def test_unknown_saved_device_is_offline(relay_server_url):
    client = await FakePeer.connect(relay_server_url, "client")
    await client.send(
        "resume_request", payload={"device_id": "dev-ffffffffffffffffffffffffffffffff"}
    )
    error = await client.recv()
    assert error["payload"]["code"] == "device_offline"
    await client.close()
