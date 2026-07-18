# termhop agent tests — boots a REAL relay-server instance (as a subprocess,
# using relay-server's own venv) so handshake/end-to-end tests exercise
# actual interop rather than a mock. This is available now that relay-server
# is built — unlike when relay-server itself was being developed, there was
# nothing to test against but a fake peer.
#
# redislite (an embedded real redis-server) backs it, same technique used in
# relay-server/tests/conftest.py, avoiding a system Redis dependency here too.
import asyncio
import socket
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
import redislite

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_DIR.parent
RELAY_SERVER_DIR = REPO_ROOT / "relay-server"
RELAY_SERVER_PYTHON = RELAY_SERVER_DIR / ".venv" / "bin" / "python"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def redislite_url():
    rl = redislite.Redis()
    rl.get(b"__warmup__")
    yield f"unix://{rl.socket_file}"
    rl.shutdown()


@pytest_asyncio.fixture
async def relay_server_url(redislite_url):
    if not RELAY_SERVER_PYTHON.exists():
        pytest.skip(f"relay-server venv not found at {RELAY_SERVER_PYTHON} — run its own setup first")

    port = _free_port()
    env = {
        "DOMAIN": "test.local",
        "REDIS_URL": redislite_url,
        "PAIRING_TOKEN_TTL": "10",
        "SESSION_PENDING_TTL": "10",
        "MAX_ENVELOPE_BYTES": "262144",
        "PROTOCOL_VERSION": "2",
        "RATE_LIMIT_IP_MAX": "1000",
        "RATE_LIMIT_IP_WINDOW_S": "60",
        "RATE_LIMIT_TOKEN_MAX": "1000",
        "TOKEN_MIN_LEN": "8",
        "TOKEN_MAX_LEN": "128",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        [str(RELAY_SERVER_PYTHON), "-m", "uvicorn", "relay.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(RELAY_SERVER_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            await asyncio.sleep(0.05)
    else:
        proc.terminate()
        raise RuntimeError("relay-server subprocess failed to start listening")

    # give uvicorn's lifespan a moment past "port open" to finish startup
    await asyncio.sleep(0.2)

    yield f"ws://127.0.0.1:{port}"

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
