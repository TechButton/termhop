# termhop agent — wires a paired RelayClient to a PTYBackend: reads PTY
# output and streams it as encrypted pty_data, decrypts incoming pty_input
# and writes it to the PTY. Runs both directions concurrently; either side
# ending (PTY exit, WS close, session_close) tears down the other.
import asyncio
import logging

import websockets

from common.envelope import EnvelopeError
from common.ptybackend import PTYBackend
from common.relay_client import HandshakeError, RelayClient

_logger = logging.getLogger("termhop.agent")


async def _pump_pty_to_relay(client: RelayClient, backend: PTYBackend) -> None:
    try:
        while True:
            data = await backend.read()
            if data:
                await client.send_pty_data(data)
    except EOFError:
        exit_code = backend.wait()
        _logger.info("pty exited code=%s", exit_code)
        await client.send_session_close(reason="process_exited")


async def _pump_relay_to_pty(client: RelayClient, backend: PTYBackend) -> None:
    while True:
        envelope = await client.recv_decrypted()
        if envelope.type == "pty_input":
            plaintext = client.decrypt_payload(envelope)
            backend.write(plaintext)
        elif envelope.type == "session_resize":
            rows = envelope.payload.get("rows")
            cols = envelope.payload.get("cols")
            if rows and cols:
                backend.resize(rows, cols)
        elif envelope.type == "session_close":
            _logger.info("session_close received from peer")
            return
        elif envelope.type == "error":
            _logger.warning("relay error envelope: %s", envelope.payload)
        else:
            _logger.debug("ignoring unhandled message type=%s", envelope.type)


async def run_pty_session(client: RelayClient, backend: PTYBackend) -> None:
    """Runs until the PTY exits, the peer closes the session, or the WS
    connection drops. Both pump directions are cancelled together so
    neither leaks a dangling task."""
    to_relay = asyncio.create_task(_pump_pty_to_relay(client, backend))
    to_pty = asyncio.create_task(_pump_relay_to_pty(client, backend))

    tasks = {to_relay, to_pty}
    try:
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(
                exc,
                (
                    websockets.exceptions.ConnectionClosed,
                    HandshakeError,
                    EnvelopeError,
                ),
            ):
                raise exc
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        backend.close()
