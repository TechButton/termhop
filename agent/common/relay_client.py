# termhop agent — WebSocket client + pairing handshake state machine +
# encrypted pty_data/pty_input pump. This is the agent-side half of the
# pairing flow whose relay-side half lives in relay-server/relay/router.py —
# field names below must match that module exactly, not just PROTOCOL.md's
# prose (the relay's tests are the ground truth for wire compatibility).
import enum
import time

import websockets

from common import crypto, pairing
from common.envelope import Envelope, EnvelopeError, dump_envelope, parse_envelope


class HandshakeState(enum.Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    AWAITING_PAIR_INIT_ACK = "awaiting_pair_init_ack"
    AWAITING_PAIR_CHALLENGE = "awaiting_pair_challenge"
    PAIRED = "paired"
    STREAMING = "streaming"
    CLOSED = "closed"


class HandshakeError(Exception):
    pass


class RelayClient:
    """Connects to `<relay>/ws/agent` and drives the pairing handshake.
    After `pair()` returns, `session_key`/`session_id` are set and the
    caller can start streaming pty_data/pty_input via send_encrypted/
    recv_encrypted."""

    def __init__(self, relay_url: str, *, agent_hostname: str = "") -> None:
        self._relay_url = relay_url.rstrip("/")
        self._agent_hostname = agent_hostname
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._seq = 0

        self.state = HandshakeState.IDLE
        self.token: str | None = None
        self.session_id: str | None = None
        self._own_private_key: bytes | None = None
        self.agent_pubkey_b64: str | None = None
        self.session_key: bytes | None = None

    async def connect(self) -> None:
        self.state = HandshakeState.CONNECTING
        self._ws = await websockets.connect(f"{self._relay_url}/ws/agent")

    async def _send(self, type_: str, *, session_id: str | None, payload: dict) -> None:
        assert self._ws is not None
        self._seq += 1
        envelope = Envelope(
            v=1, type=type_, session_id=session_id, seq=self._seq, ts=int(time.time() * 1000), payload=payload
        )
        await self._ws.send(dump_envelope(envelope))

    async def _recv(self) -> Envelope:
        assert self._ws is not None
        raw = await self._ws.recv()
        try:
            return parse_envelope(raw)
        except EnvelopeError as exc:
            raise HandshakeError(f"malformed envelope from relay: {exc}") from exc

    async def send_pair_init(self) -> tuple[str, str]:
        """Generates token/keypair/session_id, sends pair_init, and returns
        (token, session_id) so the caller can build a pairing link — but
        the caller must wait for `await_pair_init_ack()` before displaying
        it (see PROTOCOL.md's race-condition note)."""
        self.token = pairing.generate_pairing_token()
        self.session_id = pairing.generate_session_id()
        self._own_private_key, own_pubkey_raw = crypto.generate_ephemeral_keypair()
        self.agent_pubkey_b64 = crypto.encode_pubkey(own_pubkey_raw)

        self.state = HandshakeState.AWAITING_PAIR_INIT_ACK
        await self._send(
            "pair_init",
            session_id=None,
            payload={
                "token": self.token,
                "agent_pubkey": self.agent_pubkey_b64,
                "session_id": self.session_id,
                "agent_hostname": self._agent_hostname,
            },
        )
        return self.token, self.session_id

    async def await_pair_init_ack(self) -> None:
        envelope = await self._recv()
        if envelope.type == "error":
            raise HandshakeError(f"relay rejected pair_init: {envelope.payload}")
        if envelope.type != "pair_init_ack":
            raise HandshakeError(f"expected pair_init_ack, got {envelope.type}")
        self.state = HandshakeState.AWAITING_PAIR_CHALLENGE

    async def await_pair_challenge_and_complete(self) -> None:
        """Waits for pair_challenge, derives the session key, and sends
        pair_complete. After this, self.session_key is set and streaming
        can begin immediately — no session_open wait (see plan: relay's own
        tests skip straight from pair_complete to pty_data/pty_input)."""
        envelope = await self._recv()
        if envelope.type == "error":
            raise HandshakeError(f"relay rejected pairing: {envelope.payload}")
        if envelope.type != "pair_challenge":
            raise HandshakeError(f"expected pair_challenge, got {envelope.type}")

        peer_pubkey_b64 = envelope.payload.get("peer_pubkey")
        if not peer_pubkey_b64:
            raise HandshakeError("pair_challenge missing payload.peer_pubkey")

        assert self._own_private_key is not None
        peer_pubkey_raw = crypto.decode_pubkey(peer_pubkey_b64)
        self.session_key = crypto.derive_session_key(self._own_private_key, peer_pubkey_raw)
        self.session_id = envelope.session_id or self.session_id

        await self._send("pair_complete", session_id=self.session_id, payload={})
        self.state = HandshakeState.PAIRED

    async def pair(self) -> tuple[str, str]:
        """Runs the full handshake: connect -> pair_init -> pair_init_ack ->
        pair_challenge -> pair_complete. Returns (token, session_id) after
        pair_init_ack, for the caller to display a pairing link — but by
        the time this returns, pairing is already complete (this method
        blocks through the whole sequence; use the granular methods above
        if the caller needs to show the link before the peer connects)."""
        await self.connect()
        token, session_id = await self.send_pair_init()
        await self.await_pair_init_ack()
        await self.await_pair_challenge_and_complete()
        self.state = HandshakeState.STREAMING
        return token, session_id

    async def send_pty_data(self, plaintext: bytes) -> None:
        assert self.session_key is not None
        nonce_b64, ciphertext_b64 = crypto.encrypt(self.session_key, plaintext)
        await self._send(
            "pty_data", session_id=self.session_id, payload={"nonce": nonce_b64, "ciphertext": ciphertext_b64}
        )

    async def recv_decrypted(self) -> Envelope:
        """Receives the next envelope. For pty_input, the caller is
        responsible for decrypting payload.ciphertext via crypto.decrypt —
        kept separate so non-data envelopes (session_close, error) pass
        through untouched."""
        return await self._recv()

    def decrypt_payload(self, envelope: Envelope) -> bytes:
        assert self.session_key is not None
        nonce_b64 = envelope.payload.get("nonce")
        ciphertext_b64 = envelope.payload.get("ciphertext")
        if not nonce_b64 or not ciphertext_b64:
            raise HandshakeError(f"{envelope.type} missing nonce/ciphertext")
        return crypto.decrypt(self.session_key, nonce_b64, ciphertext_b64)

    async def send_session_close(self, reason: str = "") -> None:
        await self._send("session_close", session_id=self.session_id, payload={"reason": reason})

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
        self.state = HandshakeState.CLOSED
