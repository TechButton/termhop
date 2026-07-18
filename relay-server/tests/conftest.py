# termhop relay tests — shared fixtures.
#
# Uses redislite (a real embedded redis-server binary, not a mock) rather than
# fakeredis, specifically so Lua-script (EVAL) tests exercise real Redis
# semantics — fakeredis's EVAL support has historical gaps that would
# undermine exactly the atomicity guarantee pairing.py depends on.
import asyncio
import socket

import pytest
import pytest_asyncio
import redislite
import uvicorn
from redis.asyncio import Redis

from relay.config import Config
from relay.main import create_app


@pytest.fixture(scope="session")
def redislite_url():
    rl = redislite.Redis()
    rl.get(b"__warmup__")  # force the embedded server to actually start
    socket_file = rl.socket_file
    yield f"unix://{socket_file}"
    rl.shutdown()


@pytest_asyncio.fixture
async def redis_client(redislite_url):
    client = Redis.from_url(redislite_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def test_config(redislite_url):
    return Config(
        domain="test.local",
        redis_url=redislite_url,
        pairing_token_ttl_s=2,
        session_pending_ttl_s=2,
        max_envelope_bytes=262144,
        protocol_version=2,
        rate_limit_ip_max=5,
        rate_limit_ip_window_s=2,
        rate_limit_token_max=3,
        token_min_len=8,
        token_max_len=128,
        release="test",
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def relay_server_url(test_config, redis_client, monkeypatch):
    """Boots a real uvicorn instance (in-process, background task) wired to
    the redislite-backed test_config, so tests exercise the actual WS
    connect/parse/route/send path end to end rather than calling handlers
    directly. Depends on redis_client (unused directly) so its per-test
    flushdb runs first — otherwise rate-limit counters from earlier tests
    (same IP, same redislite instance) leak across tests."""
    monkeypatch.setenv("DOMAIN", test_config.domain)
    monkeypatch.setenv("REDIS_URL", test_config.redis_url)
    monkeypatch.setenv("PAIRING_TOKEN_TTL", str(test_config.pairing_token_ttl_s))
    monkeypatch.setenv("SESSION_PENDING_TTL", str(test_config.session_pending_ttl_s))
    monkeypatch.setenv("MAX_ENVELOPE_BYTES", str(test_config.max_envelope_bytes))
    monkeypatch.setenv("PROTOCOL_VERSION", str(test_config.protocol_version))
    monkeypatch.setenv("RATE_LIMIT_IP_MAX", str(test_config.rate_limit_ip_max))
    monkeypatch.setenv(
        "RATE_LIMIT_IP_WINDOW_S", str(test_config.rate_limit_ip_window_s)
    )
    monkeypatch.setenv("RATE_LIMIT_TOKEN_MAX", str(test_config.rate_limit_token_max))
    monkeypatch.setenv("TOKEN_MIN_LEN", str(test_config.token_min_len))
    monkeypatch.setenv("TOKEN_MAX_LEN", str(test_config.token_max_len))

    port = _free_port()
    app = create_app()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    else:
        raise RuntimeError("relay test server failed to start")

    yield f"ws://127.0.0.1:{port}"

    server.should_exit = True
    await task
