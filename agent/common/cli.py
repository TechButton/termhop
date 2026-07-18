"""Shared command-line flow for the Linux, macOS, and Windows agents."""

import argparse
import asyncio
import logging
import os
import socket
import sys
from collections.abc import Callable

from common import pairing
from common.config import AgentConfig, load_config, save_config
from common.pairing_link import build_pairing_uri
from common.ptybackend import PTYBackend
from common.relay_client import HandshakeError, RelayClient
from common.session_pump import run_pty_session


async def pair_and_stream(
    relay_url: str,
    *,
    config: AgentConfig,
    backend_factory: Callable[[], PTYBackend],
    shell_env_var: str,
    default_shell: str,
) -> int:
    hostname = socket.gethostname()
    client = RelayClient(relay_url, agent_hostname=hostname)

    await client.connect()
    if config.device_id and config.device_secret:
        print(f"termhop agent reconnecting saved device {config.device_id}.")
        await client.send_resume_init(
            device_id=config.device_id, device_secret=config.device_secret
        )
        await client.await_resume_and_complete()
        print("Saved client reconnected. Starting a new shell after agent restart.")
        backend = backend_factory()
        backend.spawn([os.environ.get(shell_env_var, default_shell)])
        await run_pty_session(client, backend)
        await client.close()
        return 0

    config.device_id = pairing.generate_device_id()
    config.device_secret = pairing.generate_pairing_secret()
    token, session_id = await client.send_pair_init(device_id=config.device_id)
    await client.await_pair_init_ack()

    assert client.pairing_secret is not None
    assert client.agent_pubkey_b64 is not None
    pairing_uri = build_pairing_uri(
        relay_url,
        token,
        hostname,
        client.pairing_secret,
        client.agent_pubkey_b64,
        session_id,
    )
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
        await client.close()
        return 1

    # Send the long-lived credential through the newly authenticated encrypted
    # channel. It is deliberately different from the short-lived pairing-link
    # secret, so an old leaked link cannot reconnect after its token expires.
    await client.send_device_credential(config.device_id, config.device_secret)
    # Persist only after both endpoints have authenticated the handshake; an
    # interrupted/failed first pairing must not strand the agent in resume
    # mode with a credential no client ever received.
    save_config(config)
    print("Paired. Starting shell session.")
    backend = backend_factory()
    backend.spawn([os.environ.get(shell_env_var, default_shell)])
    await run_pty_session(client, backend)
    await client.close()
    return 0


def run_cli(
    *,
    backend_factory: Callable[[], PTYBackend],
    shell_env_var: str,
    default_shell: str,
) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(prog="termhop-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    pair_parser = subparsers.add_parser(
        "pair", help="Pair with a client and start streaming a shell session"
    )
    pair_parser.add_argument(
        "--relay",
        help="Relay URL, e.g. wss://relay.example.com (persisted after first use)",
    )
    pair_parser.add_argument(
        "--new-pairing",
        action="store_true",
        help="rotate the saved device credential and pair a new client",
    )
    args = parser.parse_args()

    config = load_config()
    relay_url = args.relay or config.relay_url
    if not relay_url:
        print(
            "No relay URL given and none persisted — pass --relay wss://...",
            file=sys.stderr,
        )
        return 1
    if args.relay:
        config.relay_url = args.relay
        save_config(config)
    if args.new_pairing:
        config.device_id = None
        config.device_secret = None
        save_config(config)

    try:
        return asyncio.run(
            pair_and_stream(
                relay_url,
                config=config,
                backend_factory=backend_factory,
                shell_env_var=shell_env_var,
                default_shell=default_shell,
            )
        )
    except HandshakeError as exc:
        print(f"Pairing failed: {exc}", file=sys.stderr)
        return 1
