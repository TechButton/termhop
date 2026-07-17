# termhop agent (Linux) CLI — `termhop-agent pair --relay wss://...`.
#
# Scope for this build step (PROJECT_PLAN.md step 2): pair once, then spawn
# and stream exactly one PTY until it exits or the peer disconnects. No
# persisted device key yet, so every restart re-pairs from scratch — this is
# a known operational gap (see agent/linux/README.md), not an oversight.
import argparse
import asyncio
import logging
import os
import socket
import sys
import urllib.parse

from common.config import load_config, save_config
from common.relay_client import HandshakeError, RelayClient
from common.session_pump import run_pty_session
from linux.pty_backend import PtyLinuxBackend

_logger = logging.getLogger("termhop.agent")


def _build_pairing_uri(relay_url: str, token: str, hostname: str) -> str:
    """termhop://pair?relay=...&token=...&hostname=... — see
    client/src/lib/pairingLink.js for the decoder this must match exactly."""
    query = urllib.parse.urlencode({"relay": relay_url, "token": token, "hostname": hostname})
    return f"termhop://pair?{query}"


async def _pair_and_stream(relay_url: str) -> int:
    hostname = socket.gethostname()
    client = RelayClient(relay_url, agent_hostname=hostname)

    await client.connect()
    token, session_id = await client.send_pair_init()
    await client.await_pair_init_ack()

    pairing_uri = _build_pairing_uri(relay_url, token, hostname)
    print("termhop agent ready to pair.")
    print(f"  relay:      {relay_url}")
    print(f"  hostname:   {hostname}")
    print(f"  token:      {token}")
    print(f"  session_id: {session_id}")
    print(f"  link:       {pairing_uri}")
    print("Waiting for a client to pair...")

    try:
        await client.await_pair_challenge_and_complete()
    except HandshakeError as exc:
        print(f"Pairing failed: {exc}", file=sys.stderr)
        return 1

    print("Paired. Starting shell session.")

    backend = PtyLinuxBackend()
    shell = os.environ.get("SHELL", "/bin/bash")
    backend.spawn([shell])

    await run_pty_session(client, backend)
    await client.close()
    return 0


def _cmd_pair(args: argparse.Namespace) -> int:
    config = load_config()
    relay_url = args.relay or config.relay_url
    if not relay_url:
        print("No relay URL given and none persisted — pass --relay wss://...", file=sys.stderr)
        return 1

    if args.relay:
        config.relay_url = args.relay
        save_config(config)

    return asyncio.run(_pair_and_stream(relay_url))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="termhop-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pair_parser = subparsers.add_parser("pair", help="Pair with a client and start streaming a shell session")
    pair_parser.add_argument("--relay", help="Relay URL, e.g. wss://relay.example.com (persisted after first use)")
    pair_parser.set_defaults(func=_cmd_pair)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
