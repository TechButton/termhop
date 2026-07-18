# termhop relay — message dispatch. This is deliberately the thinnest,
# most auditable module: for routable types it does nothing but "look up the
# peer for this session_id and forward the envelope" — no inspection of
# `payload` contents for any type, since a routing bug here is the one way
# the relay could misdeliver key material during the handshake.
#
# Session-id convention (a clarification beyond PROTOCOL.md's current text —
# see relay-server task tracking / PROTOCOL.md update):
#   - pair_init: envelope-level session_id is null. The agent generates its
#     own session_id and includes it in payload.session_id, alongside its
#     agent-generated pairing token (payload.token) and ephemeral pubkey
#     (payload.agent_pubkey).
#   - pair_request: envelope-level session_id is null. payload carries
#     {token, client_pubkey}. The relay looks up session_id via the token.
#   - From pair_challenge onward, envelope-level session_id is populated and
#     used by both sides (and the relay) to address every later message.
import base64
import binascii
import re
from dataclasses import dataclass

from fastapi import WebSocket
from redis.asyncio import Redis

from relay.config import Config
from relay.envelope import ROUTABLE_TYPES, Envelope
from relay.errors import RelayError, TokenAlreadyUsed, TokenInvalid, TokenNotFound
from relay.logging_utils import log_event
from relay.pairing import (
    consume_token,
    create_session_record,
    delete_token,
    issue_token,
    mark_session_established,
    set_session_state,
    validate_token_format,
)
from relay.ratelimit import check_ip_rate_limit, check_token_rate_limit
from relay.session_registry import Role, SessionRegistry


@dataclass
class ConnectionContext:
    ws: WebSocket
    role: Role
    peer_ip: str
    redis: Redis
    cfg: Config
    registry: SessionRegistry
    session_id: str | None = None
    last_seq: int = 0


_SESSION_ID_RE = re.compile(r"^sess-[A-Za-z0-9_-]{1,64}$")
_DEVICE_ID_RE = re.compile(r"^dev-[a-f0-9]{32}$")
_ROLE_TYPES = {
    "agent": {
        "pair_init",
        "pair_complete",
        "resume_init",
        "resume_challenge",
        "resume_complete",
        "device_credential",
        "pty_data",
        "session_list",
        "session_close",
        "idle_alert",
        "port_forward_data",
        "port_forward_close",
    },
    "client": {
        "pair_request",
        "resume_request",
        "resume_proof",
        "pty_input",
        "session_open",
        "session_resize",
        "session_close",
        "port_forward_request",
        "port_forward_data",
        "port_forward_close",
    },
}


def _valid_base64_size(value: object, size: int) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return len(base64.b64decode(value, validate=True)) == size
    except (binascii.Error, ValueError):
        return False


def _valid_session_id(value: object) -> bool:
    return isinstance(value, str) and _SESSION_ID_RE.fullmatch(value) is not None


async def send_envelope(ws: WebSocket, envelope: Envelope) -> None:
    await ws.send_text(envelope.model_dump_json())


def _envelope(
    *, type_: str, session_id: str | None, seq: int, ts: int, payload: dict
) -> Envelope:
    return Envelope(
        v=2, type=type_, session_id=session_id, seq=seq, ts=ts, payload=payload
    )


async def _send_error(ctx: ConnectionContext, code: str, message: str) -> None:
    await send_envelope(
        ctx.ws,
        _envelope(
            type_="error",
            session_id=ctx.session_id,
            seq=0,
            ts=0,
            payload={"code": code, "message": message},
        ),
    )


async def handle_pair_init(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.role != "agent":
        await _send_error(
            ctx, "protocol_error", "pair_init only valid on the agent connection"
        )
        return
    if ctx.session_id is not None:
        await _send_error(
            ctx, "protocol_error", "connection is already bound to a session"
        )
        return

    token = envelope.payload.get("token", "")
    agent_pubkey = envelope.payload.get("agent_pubkey", "")
    session_id = envelope.payload.get("session_id", "")
    agent_hostname = envelope.payload.get("agent_hostname", "")

    if not session_id:
        await _send_error(
            ctx, "protocol_error", "pair_init.payload.session_id is required"
        )
        return
    if not _valid_session_id(session_id):
        await _send_error(
            ctx,
            "protocol_error",
            "session_id must be sess- followed by 1-64 url-safe characters",
        )
        return
    if not _valid_base64_size(agent_pubkey, 32):
        await _send_error(
            ctx,
            "protocol_error",
            "agent_pubkey must be standard base64 encoding of 32 bytes",
        )
        return

    # Reserve the in-process route before the first await so a concurrent
    # pair_init cannot create Redis state for the same session identifier.
    try:
        ctx.registry.attach(session_id, "agent", ctx.ws)
    except ValueError:
        await _send_error(ctx, "session_conflict", "session_id is already connected")
        return
    ctx.session_id = session_id

    try:
        await check_ip_rate_limit(ctx.redis, ctx.cfg, ctx.peer_ip)
        validate_token_format(token, ctx.cfg)
        await issue_token(
            ctx.redis,
            ctx.cfg,
            token=token,
            agent_pubkey=agent_pubkey,
            session_id=session_id,
            agent_hostname=agent_hostname,
        )
        try:
            await create_session_record(ctx.redis, ctx.cfg, session_id)
        except Exception:
            await delete_token(ctx.redis, token)
            raise
    except Exception:
        ctx.registry.detach(session_id, "agent")
        ctx.session_id = None
        raise
    log_event(
        "pair_init", session_id=session_id, msg_type="pair_init", peer_ip=ctx.peer_ip
    )

    # Registration must be confirmed before the agent displays the QR/pairing
    # link — otherwise a fast client pair_request can race ahead of the
    # relay's own bookkeeping. `pair_init_ack` is a relay-only addition to the
    # documented pairing vocabulary (see PROTOCOL.md update).
    await send_envelope(
        ctx.ws,
        _envelope(
            type_="pair_init_ack",
            session_id=session_id,
            seq=0,
            ts=envelope.ts,
            payload={},
        ),
    )


async def handle_pair_request(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.role != "client":
        await _send_error(
            ctx, "protocol_error", "pair_request only valid on the client connection"
        )
        return
    if ctx.session_id is not None:
        await _send_error(
            ctx, "protocol_error", "connection is already bound to a session"
        )
        return

    token = envelope.payload.get("token", "")
    client_pubkey = envelope.payload.get("client_pubkey", "")
    client_proof = envelope.payload.get("client_proof", "")
    if not client_pubkey or not client_proof:
        await _send_error(
            ctx,
            "protocol_error",
            "pair_request requires client_pubkey and client_proof",
        )
        return
    if not _valid_base64_size(client_pubkey, 32) or not _valid_base64_size(
        client_proof, 32
    ):
        await _send_error(
            ctx,
            "protocol_error",
            "client_pubkey and client_proof must each encode exactly 32 bytes",
        )
        return

    await check_ip_rate_limit(ctx.redis, ctx.cfg, ctx.peer_ip)
    await check_token_rate_limit(ctx.redis, ctx.cfg, token)

    fields = await consume_token(ctx.redis, token)
    session_id = fields["session_id"]
    agent_pubkey = fields["agent_pubkey"]
    agent_hostname = fields.get("agent_hostname", "")

    slot = ctx.registry.get(session_id)
    if slot is None or slot.agent is None:
        await _send_error(
            ctx, "session_not_found", "agent for this session is no longer connected"
        )
        return

    try:
        ctx.registry.attach(session_id, "client", ctx.ws)
    except ValueError:
        await _send_error(
            ctx, "session_conflict", "client is already connected for this session"
        )
        return
    ctx.session_id = session_id
    await set_session_state(ctx.redis, session_id, "handshaking")

    await send_envelope(
        ctx.ws,
        _envelope(
            type_="pair_challenge",
            session_id=session_id,
            seq=0,
            ts=envelope.ts,
            payload={"peer_pubkey": agent_pubkey, "agent_hostname": agent_hostname},
        ),
    )
    await send_envelope(
        slot.agent,
        _envelope(
            type_="pair_challenge",
            session_id=session_id,
            seq=0,
            ts=envelope.ts,
            payload={"peer_pubkey": client_pubkey, "client_proof": client_proof},
        ),
    )
    log_event(
        "pair_challenge_sent",
        session_id=session_id,
        msg_type="pair_challenge",
        peer_ip=ctx.peer_ip,
    )


async def handle_pair_complete(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.session_id is None:
        await _send_error(
            ctx, "protocol_error", "pair_complete requires an established session_id"
        )
        return
    if ctx.role != "agent":
        await _send_error(
            ctx, "protocol_error", "pair_complete is only valid from the agent"
        )
        return
    if envelope.session_id != ctx.session_id:
        await _send_error(
            ctx,
            "session_mismatch",
            "envelope session_id does not match this connection",
        )
        return
    if not envelope.payload.get("agent_proof"):
        await _send_error(ctx, "protocol_error", "pair_complete requires agent_proof")
        return
    if not _valid_base64_size(envelope.payload.get("agent_proof"), 32):
        await _send_error(
            ctx, "protocol_error", "agent_proof must encode exactly 32 bytes"
        )
        return
    peer_ws = ctx.registry.get_peer(ctx.session_id, ctx.role)
    if peer_ws is None:
        await _send_error(ctx, "session_not_found", "peer is not connected")
        return
    await send_envelope(peer_ws, envelope)
    await mark_session_established(ctx.redis, ctx.session_id)
    log_event(
        "pair_complete",
        session_id=ctx.session_id,
        msg_type="pair_complete",
        peer_ip=ctx.peer_ip,
    )


async def handle_resume_init(ctx: ConnectionContext, envelope: Envelope) -> None:
    """Register a rebooted, previously paired device without exposing its secret."""
    if ctx.role != "agent" or ctx.session_id is not None:
        await _send_error(
            ctx, "protocol_error", "resume_init requires an unbound agent connection"
        )
        return
    session_id = envelope.payload.get("session_id", "")
    device_id = envelope.payload.get("device_id", "")
    agent_pubkey = envelope.payload.get("agent_pubkey", "")
    if not _valid_session_id(session_id) or not _DEVICE_ID_RE.fullmatch(device_id):
        await _send_error(
            ctx, "protocol_error", "invalid resume session_id or device_id"
        )
        return
    if not _valid_base64_size(agent_pubkey, 32):
        await _send_error(
            ctx, "protocol_error", "agent_pubkey must encode exactly 32 bytes"
        )
        return
    try:
        ctx.registry.attach(session_id, "agent", ctx.ws)
        ctx.registry.register_device(device_id, session_id)
    except ValueError:
        ctx.registry.detach(session_id, "agent")
        await _send_error(
            ctx, "session_conflict", "device or session is already connected"
        )
        return
    ctx.session_id = session_id
    await send_envelope(
        ctx.ws,
        _envelope(
            type_="resume_init_ack",
            session_id=session_id,
            seq=0,
            ts=envelope.ts,
            payload={},
        ),
    )


async def handle_resume_request(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.role != "client" or ctx.session_id is not None:
        await _send_error(
            ctx,
            "protocol_error",
            "resume_request requires an unbound client connection",
        )
        return
    device_id = envelope.payload.get("device_id", "")
    session_id = ctx.registry.session_for_device(device_id)
    slot = ctx.registry.get(session_id) if session_id else None
    if session_id is None or slot is None or slot.agent is None:
        await _send_error(
            ctx, "device_offline", "saved device is not currently connected"
        )
        return
    try:
        ctx.registry.attach(session_id, "client", ctx.ws)
    except ValueError:
        await _send_error(
            ctx, "session_conflict", "device already has a connected client"
        )
        return
    ctx.session_id = session_id
    # The relay forwards the agent's fresh public metadata; the following
    # endpoint proofs detect any malicious substitution.
    agent_slot = slot.agent
    await send_envelope(
        agent_slot,
        _envelope(
            type_="resume_request",
            session_id=session_id,
            seq=0,
            ts=envelope.ts,
            payload={},
        ),
    )


async def handle_resume_proof(ctx: ConnectionContext, envelope: Envelope) -> None:
    if (
        ctx.role != "client"
        or ctx.session_id is None
        or envelope.session_id != ctx.session_id
    ):
        await _send_error(
            ctx, "protocol_error", "resume_proof requires the bound client session"
        )
        return
    if not _valid_base64_size(
        envelope.payload.get("client_pubkey"), 32
    ) or not _valid_base64_size(envelope.payload.get("client_proof"), 32):
        await _send_error(
            ctx, "protocol_error", "resume key and proof must each encode 32 bytes"
        )
        return
    peer = ctx.registry.get_peer(ctx.session_id, "client")
    if peer is None:
        await _send_error(ctx, "device_offline", "saved device disconnected")
        return
    await send_envelope(peer, envelope)


async def handle_resume_challenge(ctx: ConnectionContext, envelope: Envelope) -> None:
    if (
        ctx.role != "agent"
        or ctx.session_id is None
        or envelope.session_id != ctx.session_id
    ):
        await _send_error(
            ctx, "protocol_error", "resume_challenge requires the bound agent session"
        )
        return
    if not _valid_base64_size(envelope.payload.get("agent_pubkey"), 32):
        await _send_error(ctx, "protocol_error", "agent_pubkey must encode 32 bytes")
        return
    peer = ctx.registry.get_peer(ctx.session_id, "agent")
    if peer is None:
        await _send_error(ctx, "session_not_found", "client disconnected")
        return
    await send_envelope(peer, envelope)


async def handle_resume_complete(ctx: ConnectionContext, envelope: Envelope) -> None:
    if (
        ctx.role != "agent"
        or ctx.session_id is None
        or envelope.session_id != ctx.session_id
    ):
        await _send_error(
            ctx, "protocol_error", "resume_complete requires the bound agent session"
        )
        return
    if not _valid_base64_size(envelope.payload.get("agent_proof"), 32):
        await _send_error(ctx, "protocol_error", "agent_proof must encode 32 bytes")
        return
    peer = ctx.registry.get_peer(ctx.session_id, "agent")
    if peer is None:
        await _send_error(ctx, "session_not_found", "client disconnected")
        return
    await send_envelope(peer, envelope)


async def handle_routable(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.session_id is None:
        await _send_error(ctx, "protocol_error", f"{envelope.type} requires session_id")
        return
    if envelope.session_id != ctx.session_id:
        await _send_error(
            ctx,
            "session_mismatch",
            "envelope session_id does not match this connection",
        )
        return
    session_id = ctx.session_id

    peer_ws = ctx.registry.get_peer(session_id, ctx.role)
    if peer_ws is None:
        await _send_error(ctx, "session_not_found", "peer is not connected")
        return

    await send_envelope(peer_ws, envelope)

    byte_count = len(envelope.model_dump_json())
    log_event(
        "routed",
        session_id=session_id,
        msg_type=envelope.type,
        byte_count=byte_count,
        peer_ip=ctx.peer_ip,
    )

    if envelope.type == "session_close":
        await teardown_session(ctx, session_id)


async def teardown_session(ctx: ConnectionContext, session_id: str) -> None:
    from relay.pairing import delete_session_record

    ctx.registry.remove(session_id)
    await delete_session_record(ctx.redis, session_id)
    log_event(
        "session_closed",
        session_id=session_id,
        msg_type="session_close",
        peer_ip=ctx.peer_ip,
    )


_DISPATCH = {
    "pair_init": handle_pair_init,
    "pair_request": handle_pair_request,
    "pair_complete": handle_pair_complete,
    "resume_init": handle_resume_init,
    "resume_request": handle_resume_request,
    "resume_challenge": handle_resume_challenge,
    "resume_proof": handle_resume_proof,
    "resume_complete": handle_resume_complete,
}


async def dispatch(ctx: ConnectionContext, envelope: Envelope) -> None:
    if envelope.type not in _ROLE_TYPES[ctx.role]:
        await _send_error(
            ctx,
            "protocol_error",
            f"{envelope.type} is not valid from the {ctx.role} role",
        )
        return
    handler = _DISPATCH.get(envelope.type)
    if handler is not None:
        try:
            await handler(ctx, envelope)
        except (TokenNotFound, TokenAlreadyUsed) as exc:
            await _send_error(ctx, "token_invalid", str(exc))
        except TokenInvalid as exc:
            await _send_error(ctx, "token_invalid", str(exc))
        except RelayError as exc:
            await _send_error(ctx, "rate_limited", str(exc))
        return

    if envelope.type in ROUTABLE_TYPES:
        await handle_routable(ctx, envelope)
        return

    await _send_error(
        ctx, "unknown_type", f"unrecognized message type: {envelope.type}"
    )
