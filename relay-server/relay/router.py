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


async def send_envelope(ws: WebSocket, envelope: Envelope) -> None:
    await ws.send_text(envelope.model_dump_json())


def _envelope(*, type_: str, session_id: str | None, seq: int, ts: int, payload: dict) -> Envelope:
    return Envelope(v=1, type=type_, session_id=session_id, seq=seq, ts=ts, payload=payload)


async def _send_error(ctx: ConnectionContext, code: str, message: str) -> None:
    await send_envelope(
        ctx.ws,
        _envelope(type_="error", session_id=ctx.session_id, seq=0, ts=0, payload={"code": code, "message": message}),
    )


async def handle_pair_init(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.role != "agent":
        await _send_error(ctx, "protocol_error", "pair_init only valid on the agent connection")
        return

    token = envelope.payload.get("token", "")
    agent_pubkey = envelope.payload.get("agent_pubkey", "")
    session_id = envelope.payload.get("session_id", "")
    agent_hostname = envelope.payload.get("agent_hostname", "")

    if not session_id:
        await _send_error(ctx, "protocol_error", "pair_init.payload.session_id is required")
        return

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
    await create_session_record(ctx.redis, ctx.cfg, session_id)
    ctx.registry.attach(session_id, "agent", ctx.ws)
    ctx.session_id = session_id
    log_event("pair_init", session_id=session_id, msg_type="pair_init", peer_ip=ctx.peer_ip)

    # Registration must be confirmed before the agent displays the QR/pairing
    # link — otherwise a fast client pair_request can race ahead of the
    # relay's own bookkeeping. `pair_init_ack` is a relay-only addition to the
    # documented pairing vocabulary (see PROTOCOL.md update).
    await send_envelope(
        ctx.ws, _envelope(type_="pair_init_ack", session_id=session_id, seq=0, ts=envelope.ts, payload={})
    )


async def handle_pair_request(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.role != "client":
        await _send_error(ctx, "protocol_error", "pair_request only valid on the client connection")
        return

    token = envelope.payload.get("token", "")
    client_pubkey = envelope.payload.get("client_pubkey", "")

    await check_ip_rate_limit(ctx.redis, ctx.cfg, ctx.peer_ip)
    await check_token_rate_limit(ctx.redis, ctx.cfg, token)

    fields = await consume_token(ctx.redis, token)
    session_id = fields["session_id"]
    agent_pubkey = fields["agent_pubkey"]
    agent_hostname = fields.get("agent_hostname", "")

    slot = ctx.registry.get(session_id)
    if slot is None or slot.agent is None:
        await _send_error(ctx, "session_not_found", "agent for this session is no longer connected")
        return

    ctx.registry.attach(session_id, "client", ctx.ws)
    ctx.session_id = session_id
    await set_session_state(ctx.redis, session_id, "handshaking")

    await send_envelope(
        ctx.ws,
        _envelope(
            type_="pair_challenge", session_id=session_id, seq=0, ts=envelope.ts,
            payload={"peer_pubkey": agent_pubkey, "agent_hostname": agent_hostname},
        ),
    )
    await send_envelope(
        slot.agent,
        _envelope(
            type_="pair_challenge", session_id=session_id, seq=0, ts=envelope.ts,
            payload={"peer_pubkey": client_pubkey},
        ),
    )
    log_event("pair_challenge_sent", session_id=session_id, msg_type="pair_challenge", peer_ip=ctx.peer_ip)


async def handle_pair_complete(ctx: ConnectionContext, envelope: Envelope) -> None:
    if ctx.session_id is None:
        await _send_error(ctx, "protocol_error", "pair_complete requires an established session_id")
        return
    await mark_session_established(ctx.redis, ctx.session_id)
    log_event("pair_complete", session_id=ctx.session_id, msg_type="pair_complete", peer_ip=ctx.peer_ip)


async def handle_routable(ctx: ConnectionContext, envelope: Envelope) -> None:
    session_id = envelope.session_id or ctx.session_id
    if session_id is None:
        await _send_error(ctx, "protocol_error", f"{envelope.type} requires session_id")
        return

    peer_ws = ctx.registry.get_peer(session_id, ctx.role)
    if peer_ws is None:
        await _send_error(ctx, "session_not_found", "peer is not connected")
        return

    await send_envelope(peer_ws, envelope)

    byte_count = len(envelope.model_dump_json())
    log_event(
        "routed", session_id=session_id, msg_type=envelope.type, byte_count=byte_count, peer_ip=ctx.peer_ip
    )

    if envelope.type == "session_close":
        await teardown_session(ctx, session_id)


async def teardown_session(ctx: ConnectionContext, session_id: str) -> None:
    from relay.pairing import delete_session_record

    ctx.registry.remove(session_id)
    await delete_session_record(ctx.redis, session_id)
    log_event("session_closed", session_id=session_id, msg_type="session_close", peer_ip=ctx.peer_ip)


_DISPATCH = {
    "pair_init": handle_pair_init,
    "pair_request": handle_pair_request,
    "pair_complete": handle_pair_complete,
}


async def dispatch(ctx: ConnectionContext, envelope: Envelope) -> None:
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

    await _send_error(ctx, "unknown_type", f"unrecognized message type: {envelope.type}")
