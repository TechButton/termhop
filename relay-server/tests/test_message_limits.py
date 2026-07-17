# termhop relay tests — oversized/malformed/version-mismatch envelope
# rejection (connection closed with policy-violation, not silently truncated
# or misparsed).
import json

import pytest
import websockets

from tests.fake_peer import FakePeer

pytestmark = pytest.mark.asyncio

_POLICY_VIOLATION = 1008


async def test_oversized_envelope_closes_connection(relay_server_url, test_config):
    agent = await FakePeer.connect(relay_server_url, "agent")
    oversized_payload = "x" * (test_config.max_envelope_bytes + 1000)
    raw = json.dumps(
        {"v": 1, "type": "pair_init", "session_id": None, "seq": 1, "ts": 1, "payload": {"blob": oversized_payload}}
    )
    await agent.send_raw(raw)
    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await agent.recv()
    assert agent._ws.close_code == _POLICY_VIOLATION


async def test_malformed_json_closes_connection(relay_server_url):
    client = await FakePeer.connect(relay_server_url, "client")
    await client.send_raw("not valid json{{{")
    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await client.recv()
    assert client._ws.close_code == _POLICY_VIOLATION


async def test_missing_required_field_closes_connection(relay_server_url):
    agent = await FakePeer.connect(relay_server_url, "agent")
    raw = json.dumps({"v": 1, "type": "pair_init"})  # missing seq/ts
    await agent.send_raw(raw)
    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await agent.recv()
    assert agent._ws.close_code == _POLICY_VIOLATION


async def test_version_mismatch_closes_connection(relay_server_url):
    client = await FakePeer.connect(relay_server_url, "client")
    raw = json.dumps({"v": 99, "type": "pair_request", "session_id": None, "seq": 1, "ts": 1, "payload": {}})
    await client.send_raw(raw)
    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await client.recv()
    assert client._ws.close_code == _POLICY_VIOLATION
