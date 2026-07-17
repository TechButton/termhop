# termhop agent (Windows) CLI — `termhop-agent pair --relay wss://...`.
#
# Parallel structure to agent/linux/main.py and agent/macos/main.py — the
# PTY backend import and default-shell fallback differ. No $SHELL on
# Windows; COMSPEC is the actual Windows analog (nearly always set to
# cmd.exe) and matches the same env-var-driven default-lookup pattern the
# other two platforms use. Deliberately NOT defaulting to
# powershell.exe/pwsh.exe — that's a second binary-name ambiguity across
# PowerShell versions; multi-shell selection belongs in a future per-
# session feature, not this agent's zero-argument default.
#
# Scope for this build step (PROJECT_PLAN.md step 4): pair once, then spawn
# and stream exactly one PTY until it exits or the peer disconnects. No
# persisted device key yet, so every restart re-pairs from scratch — this is
# a known operational gap (see agent/windows/README.md), not an oversight.
import argparse
import asyncio
import logging
import os
import socket
import sys

from common.config import load_config, save_config
from common.pairing_link import build_pairing_uri
from common.relay_client import HandshakeError, RelayClient
from common.session_pump import run_pty_session
from windows.pty_backend import PtyWindowsBackend

_logger = logging.getLogger("termhop.agent")


async def _pair_and_stream(relay_url: str) -> int:
    hostname = socket.gethostname()
    client = RelayClient(relay_url, agent_hostname=hostname)

    await client.connect()
    token, session_id = await client.send_pair_init()
    await client.await_pair_init_ack()

    pairing_uri = build_pairing_uri(relay_url, token, hostname)
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

    backend = PtyWindowsBackend()
    shell = os.environ.get("COMSPEC", "cmd.exe")
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
