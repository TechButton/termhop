# termhop relay tests — automates SECURITY.md's pre-release checklist item:
# "confirm relay cannot decrypt traffic even with DB + log access." Sends a
# unique canary marker as ciphertext through a full session, then asserts it
# appears in neither captured logs nor any Redis key's value.
import logging

import pytest

from tests.fake_peer import FakePeer

pytestmark = pytest.mark.asyncio

CANARY = "CANARY-PAYLOAD-MARKER-8f3a1c9e"


async def _dump_all_redis_values(redis_client) -> list[str]:
    values: list[str] = []
    async for key in redis_client.scan_iter("*"):
        key_type = await redis_client.type(key)
        if key_type == "hash":
            values.extend((await redis_client.hgetall(key)).values())
        elif key_type == "string":
            values.append(await redis_client.get(key))
        elif key_type == "set":
            values.extend(await redis_client.smembers(key))
        elif key_type == "zset":
            values.extend(await redis_client.zrange(key, 0, -1))
        elif key_type == "list":
            values.extend(await redis_client.lrange(key, 0, -1))
    return values


async def test_canary_marker_absent_from_logs_and_redis(relay_server_url, redis_client, caplog):
    caplog.set_level(logging.DEBUG, logger="relay")

    session_id = "sess-canary"
    token = "tok_" + "n" * 16
    agent = await FakePeer.connect(relay_server_url, "agent")
    client = await FakePeer.connect(relay_server_url, "client")

    # Pubkeys are intentionally NOT canaried — they're not secret (SECURITY.md:
    # ephemeral DH public keys are safe for the relay to store/route) and are
    # expected to land in Redis by design, so canarying them would be a false
    # positive for this test. Only the actual ciphertext payload below stands
    # in for genuinely sensitive content that must never be persisted/logged.
    await agent.send("pair_init", payload={"token": token, "agent_pubkey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "session_id": session_id})
    await agent.recv()  # pair_init_ack
    await client.send(
        "pair_request", payload={"token": token, "client_pubkey": "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=", "client_proof": "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI="}
    )
    await client.recv()  # pair_challenge
    await agent.recv()  # pair_challenge
    await agent.send("pair_complete", session_id=session_id, payload={"agent_proof": "AwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwM="})
    await client.recv()  # pair_complete

    await agent.send("pty_data", session_id=session_id, payload={"nonce": "n", "ciphertext": CANARY})
    await client.recv()

    await client.send("session_close", session_id=session_id, payload={})
    await agent.recv()

    await agent.close()
    await client.close()

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert CANARY not in log_text, "canary marker leaked into relay logs"

    redis_values = await _dump_all_redis_values(redis_client)
    assert all(CANARY not in v for v in redis_values), "canary marker leaked into a Redis value"
