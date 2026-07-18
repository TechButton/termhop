#!/usr/bin/env python3
"""termhop client E2E harness — boots a REAL relay-server + REAL Linux agent
as subprocesses (redislite-backed, no system Redis needed), captures the
agent's printed pairing URI, and prints it on stdout as PAIRING_LINK=<uri>
once ready. Stays alive (backing the E2E test's live session) until killed.

Run with agent/.venv/bin/python (needs redislite + the agent's own deps;
relay-server itself is launched via ITS OWN venv, same as
agent/tests/conftest.py does).
"""
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RELAY_SERVER_DIR = REPO_ROOT / "relay-server"
RELAY_SERVER_PYTHON = RELAY_SERVER_DIR / ".venv" / "bin" / "python"
AGENT_DIR = REPO_ROOT / "agent"
AGENT_PYTHON = AGENT_DIR / ".venv" / "bin" / "python"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    import redislite

    rl = redislite.Redis()
    rl.get(b"warmup")
    redis_url = f"unix://{rl.socket_file}"

    relay_port = free_port()
    relay_env = {
        "DOMAIN": "e2e.local",
        "REDIS_URL": redis_url,
        "PAIRING_TOKEN_TTL": "300",
        "SESSION_PENDING_TTL": "300",
        "MAX_ENVELOPE_BYTES": "262144",
        "PROTOCOL_VERSION": "2",
        "RATE_LIMIT_IP_MAX": "1000",
        "RATE_LIMIT_IP_WINDOW_S": "60",
        "RATE_LIMIT_TOKEN_MAX": "1000",
        "TOKEN_MIN_LEN": "8",
        "TOKEN_MAX_LEN": "128",
        "PATH": "/usr/bin:/bin",
    }
    relay_proc = subprocess.Popen(
        [str(RELAY_SERVER_PYTHON), "-m", "uvicorn", "relay.main:app", "--host", "127.0.0.1", "--port", str(relay_port)],
        cwd=str(RELAY_SERVER_DIR),
        env=relay_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", relay_port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        print("relay-server failed to start", file=sys.stderr)
        return 1
    time.sleep(0.2)

    # Never read or overwrite the developer's real saved device credential.
    # The browser test owns an isolated XDG config directory for its agent.
    agent_config = tempfile.TemporaryDirectory(prefix="termhop-e2e-agent-")
    agent_env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "XDG_CONFIG_HOME": agent_config.name}
    agent_proc = subprocess.Popen(
        [str(AGENT_PYTHON), "-u", "-m", "linux.main", "pair", "--relay", f"ws://127.0.0.1:{relay_port}"],
        cwd=str(AGENT_DIR),
        env=agent_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    pairing_link = None
    deadline = time.time() + 15
    while time.time() < deadline:
        line = agent_proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        match = re.search(r"link:\s+(termhop://\S+)", line)
        if match:
            pairing_link = match.group(1)
            break

    if not pairing_link:
        print("agent never printed a pairing link", file=sys.stderr)
        return 1

    print(f"PAIRING_LINK={pairing_link}", flush=True)
    print("READY", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        agent_proc.terminate()
        relay_proc.terminate()
        agent_config.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
