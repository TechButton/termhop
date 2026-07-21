# termhop relay — WebSocket connection lifecycle. Two routes disambiguated
# by path rather than a single endpoint branching on role for its entire
# lifetime: /ws/agent only ever plays the agent role, /ws/client only ever
# plays the client role.
import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from relay.envelope import parse_envelope
from relay.errors import EnvelopeInvalid, EnvelopeTooLarge, ProtocolVersionMismatch
from relay.logging_utils import log_event
from relay.router import ConnectionContext, dispatch, send_envelope, teardown_session
from relay.session_registry import Role

router = APIRouter()

_POLICY_VIOLATION = 1008


def _client_ip(websocket: WebSocket, trusted_proxy_ips: frozenset[str]) -> str:
    # Only trust X-Forwarded-For when the directly-connecting peer is a
    # known reverse proxy; otherwise any client could spoof the header and
    # bypass per-IP rate limiting / connection caps outright. When trusted,
    # take the last hop, i.e. the address the (single, immediate) proxy
    # itself reports as whoever connected to it.
    client = websocket.client
    peer = client.host if client else "unknown"
    if peer in trusted_proxy_ips:
        forwarded = websocket.headers.get("x-forwarded-for")
        if forwarded:
            candidate = forwarded.rsplit(",", 1)[-1].strip()
            if candidate:
                return candidate
    return peer


async def _ws_loop(websocket: WebSocket, role: Role) -> None:
    cfg = websocket.app.state.config
    if role == "client":
        origin = websocket.headers.get("origin")
        if origin is not None and origin.rstrip("/") not in cfg.client_origins:
            await websocket.close(code=_POLICY_VIOLATION, reason="origin not allowed")
            return
    peer_ip = _client_ip(websocket, cfg.trusted_proxy_ips)
    limiter = websocket.app.state.conn_limiter
    if not limiter.try_acquire(peer_ip, cfg.max_connections_per_ip):
        await websocket.close(
            code=_POLICY_VIOLATION, reason="too many connections from this address"
        )
        return
    app = websocket.app
    ctx = ConnectionContext(
        ws=websocket,
        role=role,
        peer_ip=peer_ip,
        redis=app.state.redis,
        cfg=cfg,
        registry=app.state.registry,
    )
    try:
        await websocket.accept()
        while True:
            # Every connection carries a deadline by default — including
            # before session_id is even bound, so a connection that never
            # sends a first message at all can't be held open indefinitely.
            # Two phases are deliberately exempt: "established" (the session
            # is live) and "waiting_resume" (an agent legitimately waits
            # unbounded for its owner to resume, see SESSION_LIFECYCLE.md).
            if ctx.handshake_deadline is None:
                ctx.handshake_deadline = time.monotonic() + ctx.cfg.handshake_timeout_s
            timeout = max(ctx.handshake_deadline - time.monotonic(), 0.0)
            if ctx.session_id is not None:
                slot = ctx.registry.get(ctx.session_id)
                if slot is not None and slot.phase in ("established", "waiting_resume"):
                    timeout = None
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            except TimeoutError:
                await websocket.close(
                    code=_POLICY_VIOLATION, reason="handshake timed out"
                )
                return
            try:
                envelope = parse_envelope(
                    raw, max_bytes=ctx.cfg.max_envelope_bytes, expected_version=ctx.cfg.protocol_version
                )
            except (EnvelopeTooLarge, EnvelopeInvalid, ProtocolVersionMismatch) as exc:
                log_event("envelope_rejected", session_id=ctx.session_id, peer_ip=ctx.peer_ip, error=str(exc))
                await websocket.close(code=_POLICY_VIOLATION, reason=str(exc)[:120])
                return
            if envelope.seq <= ctx.last_seq:
                log_event(
                    "sequence_rejected",
                    session_id=ctx.session_id,
                    peer_ip=ctx.peer_ip,
                    error=f"non-monotonic seq {envelope.seq}",
                )
                await websocket.close(code=_POLICY_VIOLATION, reason="sequence numbers must increase")
                return
            ctx.last_seq = envelope.seq
            await dispatch(ctx, envelope)
    except WebSocketDisconnect:
        pass
    finally:
        limiter.release(peer_ip)
        await _handle_disconnect(ctx)


async def _handle_disconnect(ctx: ConnectionContext) -> None:
    if ctx.session_id is None:
        return
    peer_ws = ctx.registry.get_peer(ctx.session_id, ctx.role)
    session_id = ctx.session_id
    ctx.registry.detach(session_id, ctx.role)
    if peer_ws is not None and peer_ws.client_state == WebSocketState.CONNECTED:
        from relay.router import _envelope

        try:
            await send_envelope(
                peer_ws, _envelope(type_="session_close", session_id=session_id, seq=0, ts=0, payload={"reason": "peer_disconnected"})
            )
        except Exception:
            pass
    await teardown_session(ctx, session_id)


@router.websocket("/ws/agent")
async def agent_endpoint(websocket: WebSocket) -> None:
    await _ws_loop(websocket, "agent")


@router.websocket("/ws/client")
async def client_endpoint(websocket: WebSocket) -> None:
    await _ws_loop(websocket, "client")
