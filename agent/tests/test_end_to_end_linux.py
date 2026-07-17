# termhop agent tests — the literal PROJECT_PLAN.md step 2 deliverable:
# "spawn one PTY, stream encrypted traffic to relay, confirm round-trip
# with a raw test client." Real relay + real PtyLinuxBackend + FakeClientPeer.
import asyncio

import pytest

from common.relay_client import RelayClient
from common.session_pump import run_pty_session
from linux.pty_backend import PtyLinuxBackend
from tests.fake_client_peer import FakeClientPeer

pytestmark = pytest.mark.asyncio


async def test_end_to_end_pty_round_trip(relay_server_url):
    agent = RelayClient(relay_server_url, agent_hostname="e2e-test-host")
    await agent.connect()
    token, _ = await agent.send_pair_init()
    await agent.await_pair_init_ack()

    client = await FakeClientPeer.connect(relay_server_url)
    await client.pair_request_and_complete(token)
    await agent.await_pair_challenge_and_complete()

    backend = PtyLinuxBackend()
    backend.spawn(["cat"])  # echoes back whatever it's fed

    pump_task = asyncio.create_task(run_pty_session(agent, backend))

    await client.send_encrypted("pty_input", b"hello from client\n")
    echoed = b""
    for _ in range(10):
        envelope = await asyncio.wait_for(client.recv(), timeout=5)
        if envelope.type == "pty_data":
            echoed += client.decrypt(envelope)
            if b"hello from client" in echoed:
                break
    # PTYs echo input (terminal-driver local echo) in addition to `cat`
    # echoing what it read, and normalize newlines to CRLF — both expected
    # PTY behaviors, not implementation bugs. The content round-tripping is
    # what this test verifies.
    assert b"hello from client" in echoed

    await client.send("session_close", session_id=client.session_id, payload={})
    await asyncio.wait_for(pump_task, timeout=5)

    await agent.close()
    await client.close()
