"""Shared command-line flow for the Linux, macOS, and Windows agents."""

import argparse
import asyncio
import logging
import os
import socket
import sys
from collections.abc import Callable
from pathlib import Path

from common import pairing
from common.config import AgentConfig, load_config, save_config
from common.pairing_link import build_pairing_uri
from common.ptybackend import PTYBackend
from common.relay_client import HandshakeError, RelayClient
from common.session_pump import run_pty_session
from common.terminal_qr import print_pairing_qr
from common.session_manager import SessionManager


def _session_manifest_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "termhop" / "sessions.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "termhop" / "sessions.json"
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "termhop" / "sessions.json"


async def _run_persistent_session(
    client: RelayClient,
    backend: PTYBackend,
    *,
    relay_url: str,
    hostname: str,
    config: AgentConfig,
) -> RelayClient:
    """Keep one PTY alive while browser relay connections detach/reconnect."""
    while backend.is_alive():
        await run_pty_session(client, backend, preserve_backend=True)
        if not backend.is_alive():
            break
        await client.close()
        while backend.is_alive():
            await asyncio.sleep(1)
            replacement = RelayClient(relay_url, agent_hostname=hostname)
            try:
                await replacement.connect()
                await replacement.send_resume_init(
                    device_id=config.device_id or "",
                    device_secret=config.device_secret or "",
                )
                await replacement.await_resume_and_complete()
                client = replacement
                break
            except Exception:
                await replacement.close()
    backend.close()
    await client.close()
    return client


async def pair_and_stream(
    relay_url: str,
    *,
    config: AgentConfig,
    backend_factory: Callable[[], PTYBackend],
    shell_env_var: str,
    default_shell: str,
    session_label: str,
) -> int:
    hostname = socket.gethostname()
    shell_cwd = os.path.expanduser("~")
    client = RelayClient(relay_url, agent_hostname=hostname)
    try:
        await client.connect()
        if config.device_id and config.device_secret:
            print(f"termhop agent reconnecting saved device {config.device_id}.")
            await client.send_resume_init(
                device_id=config.device_id, device_secret=config.device_secret
            )
            await client.await_resume_and_complete()
            print("Saved client reconnected. Starting a new shell after agent restart.")
            backend = backend_factory()
            backend.spawn([os.environ.get(shell_env_var, default_shell)], cwd=shell_cwd)
            session_manager = SessionManager(_session_manifest_path())
            session_record = session_manager.create(session_label, shell_cwd)
            session_manager.start(session_record.session_id)
            await client.send_session_list([
                {
                    "session_id": item.session_id,
                    "label": item.label,
                    "cwd": item.cwd,
                    "state": item.state,
                }
                for item in session_manager.list()
            ])
            try:
                await _run_persistent_session(
                    client, backend, relay_url=relay_url, hostname=hostname, config=config
                )
            finally:
                session_manager.complete(session_record.session_id)
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
        print_pairing_qr(pairing_uri)
        print("Waiting for a client to pair...")

        try:
            await client.await_pair_challenge_and_complete()
        except HandshakeError as exc:
            print(f"Pairing failed: {exc}", file=sys.stderr)
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
        backend.spawn([os.environ.get(shell_env_var, default_shell)], cwd=shell_cwd)
        session_manager = SessionManager(_session_manifest_path())
        session_record = session_manager.create(session_label, shell_cwd)
        session_manager.start(session_record.session_id)
        await client.send_session_list([
            {
                "session_id": item.session_id,
                "label": item.label,
                "cwd": item.cwd,
                "state": item.state,
            }
            for item in session_manager.list()
        ])
        try:
            await _run_persistent_session(
                client, backend, relay_url=relay_url, hostname=hostname, config=config
            )
        finally:
            session_manager.complete(session_record.session_id)
        return 0
    finally:
        await client.close()


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
    pair_parser.add_argument(
        "--label",
        default="Terminal session",
        help="label for the persistent terminal session",
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
                session_label=args.label,
            )
        )
    except HandshakeError as exc:
        print(f"Pairing failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nTermHop agent stopped. Your saved pairing was kept.")
        if sys.platform.startswith("linux"):
            print(
                "Run in the background with: "
                "systemctl --user enable --now termhop-agent"
            )
        return 130
