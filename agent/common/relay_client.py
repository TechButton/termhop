# termhop agent — WebSocket client + pairing handshake state machine +
# encrypted pty_data/pty_input pump. This is the agent-side half of the
# pairing flow whose relay-side half lives in relay-server/relay/router.py —
# field names below must match that module exactly, not just PROTOCOL.md's
# prose (the relay's tests are the ground truth for wire compatibility).
import enum
import json
import time
import urllib.parse

import websockets

from common import crypto, pairing
from common.envelope import Envelope, EnvelopeError, dump_envelope, parse_envelope

PROTOCOL_VERSION = 2
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


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
    After `pair()` returns, directional `session_keys` and `session_id` are
    set and the caller can start the encrypted PTY pump."""

    def __init__(self, relay_url: str, *, agent_hostname: str = "") -> None:
        parsed_url = urllib.parse.urlparse(relay_url)
        if parsed_url.scheme not in {"ws", "wss"} or not parsed_url.hostname:
            raise HandshakeError("relay URL must use ws:// or wss://")
        if parsed_url.scheme == "ws" and parsed_url.hostname not in _LOOPBACK_HOSTS:
            raise HandshakeError(
                "plaintext ws:// is allowed only for loopback development"
            )
        self._relay_url = relay_url.rstrip("/")
        self._agent_hostname = agent_hostname
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._seq = 0

        self.state = HandshakeState.IDLE
        self.token: str | None = None
        self.pairing_secret: str | None = None
        self.session_id: str | None = None
        self._own_private_key: bytes | None = None
        self.agent_pubkey_b64: str | None = None
        self.session_keys: crypto.SessionKeys | None = None
        self._transcript: bytes | None = None
        self._last_peer_encrypted_seq = 0

    async def connect(self) -> None:
        self.state = HandshakeState.CONNECTING
        self._ws = await websockets.connect(f"{self._relay_url}/ws/agent")

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def _send(
        self,
        type_: str,
        *,
        session_id: str | None,
        payload: dict,
        seq: int | None = None,
    ) -> None:
        assert self._ws is not None
        seq = self._next_seq() if seq is None else seq
        envelope = Envelope(
            v=PROTOCOL_VERSION,
            type=type_,
            session_id=session_id,
            seq=seq,
            ts=int(time.time() * 1000),
            payload=payload,
        )
        await self._ws.send(dump_envelope(envelope))

    async def _recv(self) -> Envelope:
        assert self._ws is not None
        raw = await self._ws.recv()
        try:
            envelope = parse_envelope(raw)
        except EnvelopeError as exc:
            raise HandshakeError(f"malformed envelope from relay: {exc}") from exc
        if envelope.v != PROTOCOL_VERSION:
            raise HandshakeError(
                f"relay protocol version {envelope.v} does not match client version {PROTOCOL_VERSION}"
            )
        return envelope

    async def send_pair_init(
        self, *, pairing_secret: str | None = None, device_id: str | None = None
    ) -> tuple[str, str]:
        """Generates token/keypair/session_id, sends pair_init, and returns
        (token, session_id) so the caller can build a pairing link — but
        the caller must wait for `await_pair_init_ack()` before displaying
        it (see PROTOCOL.md's race-condition note)."""
        self.token = pairing.generate_pairing_token()
        self.pairing_secret = pairing_secret or pairing.generate_pairing_secret()
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
                "device_id": device_id or "",
            },
        )
        return self.token, self.session_id

    async def send_resume_init(self, *, device_id: str, device_secret: str) -> str:
        """Advertise a previously paired device using only public routing data."""
        self.token = f"resume:{device_id}"
        self.pairing_secret = device_secret
        self.session_id = pairing.generate_session_id()
        self._own_private_key, own_pubkey_raw = crypto.generate_ephemeral_keypair()
        self.agent_pubkey_b64 = crypto.encode_pubkey(own_pubkey_raw)
        await self._send(
            "resume_init",
            session_id=None,
            payload={
                "device_id": device_id,
                "session_id": self.session_id,
                "agent_pubkey": self.agent_pubkey_b64,
                "agent_hostname": self._agent_hostname,
            },
        )
        ack = await self._recv()
        if ack.type != "resume_init_ack":
            raise HandshakeError(f"expected resume_init_ack, got {ack.type}")
        return self.session_id

    async def await_resume_and_complete(self) -> None:
        """Prove the durable secret while deriving fresh per-connection keys."""
        request = await self._recv()
        if request.type != "resume_request" or request.session_id != self.session_id:
            raise HandshakeError(f"expected resume_request, got {request.type}")
        assert self.session_id and self.agent_pubkey_b64 and self.token
        await self._send(
            "resume_challenge",
            session_id=self.session_id,
            payload={
                "agent_pubkey": self.agent_pubkey_b64,
                "agent_hostname": self._agent_hostname,
            },
        )
        proof = await self._recv()
        if proof.type != "resume_proof" or proof.session_id != self.session_id:
            raise HandshakeError(f"expected resume_proof, got {proof.type}")
        client_pubkey = proof.payload.get("client_pubkey", "")
        client_proof = proof.payload.get("client_proof", "")
        assert self._own_private_key and self.pairing_secret
        self._transcript = crypto.handshake_transcript(
            session_id=self.session_id,
            token=self.token,
            agent_pubkey_b64=self.agent_pubkey_b64,
            client_pubkey_b64=client_pubkey,
        )
        self.session_keys = crypto.derive_session_keys(
            self._own_private_key,
            crypto.decode_pubkey(client_pubkey),
            self.pairing_secret,
            self._transcript,
        )
        if not crypto.verify_pairing_proof(
            self.session_keys.proof, self._transcript, "client", client_proof
        ):
            raise HandshakeError("saved client proof is invalid")
        agent_proof = crypto.pairing_proof(
            self.session_keys.proof, self._transcript, "agent"
        )
        await self._send(
            "resume_complete",
            session_id=self.session_id,
            payload={"agent_proof": agent_proof},
        )
        self.state = HandshakeState.PAIRED

    async def await_pair_init_ack(self) -> None:
        envelope = await self._recv()
        if envelope.type == "error":
            raise HandshakeError(f"relay rejected pair_init: {envelope.payload}")
        if envelope.type != "pair_init_ack":
            raise HandshakeError(f"expected pair_init_ack, got {envelope.type}")
        self.state = HandshakeState.AWAITING_PAIR_CHALLENGE

    async def await_pair_challenge_and_complete(self) -> None:
        """Authenticates pair_challenge, derives directional keys, and sends
        pair_complete. After this, self.session_keys is set and streaming
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

        client_proof = envelope.payload.get("client_proof")
        if not client_proof:
            raise HandshakeError("pair_challenge missing payload.client_proof")
        if envelope.session_id != self.session_id:
            raise HandshakeError(
                "pair_challenge session_id does not match the pairing link"
            )

        assert self._own_private_key is not None
        assert self.agent_pubkey_b64 is not None
        assert self.pairing_secret is not None
        assert self.token is not None
        assert self.session_id is not None
        peer_pubkey_raw = crypto.decode_pubkey(peer_pubkey_b64)
        self._transcript = crypto.handshake_transcript(
            session_id=self.session_id,
            token=self.token,
            agent_pubkey_b64=self.agent_pubkey_b64,
            client_pubkey_b64=peer_pubkey_b64,
        )
        self.session_keys = crypto.derive_session_keys(
            self._own_private_key,
            peer_pubkey_raw,
            self.pairing_secret,
            self._transcript,
        )
        if not crypto.verify_pairing_proof(
            self.session_keys.proof, self._transcript, "client", client_proof
        ):
            raise HandshakeError("client pairing proof is invalid")

        agent_proof = crypto.pairing_proof(
            self.session_keys.proof, self._transcript, "agent"
        )
        await self._send(
            "pair_complete",
            session_id=self.session_id,
            payload={"agent_proof": agent_proof},
        )
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
        await self.send_encrypted("pty_data", plaintext)

    async def send_encrypted(self, type_: str, plaintext: bytes) -> None:
        """Encrypt one agent-to-client message with metadata-bound AAD."""
        assert self.session_keys is not None
        assert self.session_id is not None
        seq = self._next_seq()
        aad = crypto.message_aad(
            type_=type_,
            session_id=self.session_id,
            seq=seq,
            direction="agent_to_client",
        )
        nonce_b64, ciphertext_b64 = crypto.encrypt(
            self.session_keys.agent_to_client, plaintext, aad=aad
        )
        await self._send(
            type_,
            session_id=self.session_id,
            payload={"nonce": nonce_b64, "ciphertext": ciphertext_b64},
            seq=seq,
        )

    async def send_device_credential(self, device_id: str, device_secret: str) -> None:
        """Transfer the durable credential only inside the authenticated session."""
        payload = json.dumps(
            {"device_id": device_id, "device_secret": device_secret}
        ).encode()
        await self.send_encrypted("device_credential", payload)

    async def recv_decrypted(self) -> Envelope:
        """Receives the next envelope. For pty_input, the caller is
        responsible for decrypting payload.ciphertext via crypto.decrypt —
        kept separate so non-data envelopes (session_close, error) pass
        through untouched."""
        return await self._recv()

    def decrypt_payload(self, envelope: Envelope) -> bytes:
        assert self.session_keys is not None
        assert self.session_id is not None
        if envelope.session_id != self.session_id:
            raise HandshakeError(
                "encrypted envelope session_id does not match this connection"
            )
        if envelope.seq <= self._last_peer_encrypted_seq:
            raise HandshakeError("replayed or out-of-order encrypted envelope")
        nonce_b64 = envelope.payload.get("nonce")
        ciphertext_b64 = envelope.payload.get("ciphertext")
        if not nonce_b64 or not ciphertext_b64:
            raise HandshakeError(f"{envelope.type} missing nonce/ciphertext")
        aad = crypto.message_aad(
            type_=envelope.type,
            session_id=self.session_id,
            seq=envelope.seq,
            direction="client_to_agent",
        )
        try:
            plaintext = crypto.decrypt(
                self.session_keys.client_to_agent, nonce_b64, ciphertext_b64, aad=aad
            )
        except crypto.CryptoError as exc:
            raise HandshakeError("encrypted message authentication failed") from exc
        self._last_peer_encrypted_seq = envelope.seq
        return plaintext

    async def send_session_close(self, reason: str = "") -> None:
        await self._send(
            "session_close", session_id=self.session_id, payload={"reason": reason}
        )

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
        self.state = HandshakeState.CLOSED
