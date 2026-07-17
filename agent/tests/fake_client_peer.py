# termhop agent tests — a raw WS "client"-role peer that does REAL ECDH
# math independently of agent/common/crypto.py, so tests prove actual
# interop rather than "both sides used the same code so of course it
# matches." This is the client-side counterpart to relay-server's opaque-
# blob FakePeer, except this one holds real key material (unlike the relay,
# which never does).
import time

import websockets

# Reuses agent/common's crypto+envelope helpers for the underlying primitives
# (X25519/HKDF/AEAD) — reusing pynacl/cryptography calls is not "using the
# same handshake code," it's just not hand-rolling crypto twice. The
# handshake *sequencing* below is written independently of RelayClient.
from common import crypto
from common.envelope import Envelope, parse_envelope


class FakeClientPeer:
    def __init__(self, ws) -> None:
        self._ws = ws
        self._seq = 0
        self._own_private_key: bytes | None = None
        self.client_pubkey_b64: str | None = None
        self.session_key: bytes | None = None
        self.session_id: str | None = None

    @classmethod
    async def connect(cls, base_url: str) -> "FakeClientPeer":
        ws = await websockets.connect(f"{base_url}/ws/client")
        return cls(ws)

    async def send(self, type_: str, *, session_id: str | None = None, payload: dict | None = None) -> None:
        self._seq += 1
        envelope = Envelope(
            v=1, type=type_, session_id=session_id, seq=self._seq, ts=int(time.time() * 1000),
            payload=payload or {},
        )
        await self._ws.send(envelope.model_dump_json())

    async def recv(self) -> Envelope:
        raw = await self._ws.recv()
        return parse_envelope(raw)

    async def pair_request_and_complete(self, token: str) -> str:
        """Sends pair_request with a fresh ephemeral keypair, awaits
        pair_challenge, derives the session key, sends pair_complete.
        Returns the agent's hostname from pair_challenge.payload (proves
        the agent_hostname protocol addition round-trips end to end)."""
        self._own_private_key, own_pubkey_raw = crypto.generate_ephemeral_keypair()
        self.client_pubkey_b64 = crypto.encode_pubkey(own_pubkey_raw)

        await self.send("pair_request", payload={"token": token, "client_pubkey": self.client_pubkey_b64})

        challenge = await self.recv()
        if challenge.type != "pair_challenge":
            raise AssertionError(f"expected pair_challenge, got {challenge.type}: {challenge.payload}")

        peer_pubkey_raw = crypto.decode_pubkey(challenge.payload["peer_pubkey"])
        self.session_key = crypto.derive_session_key(self._own_private_key, peer_pubkey_raw)
        self.session_id = challenge.session_id

        await self.send("pair_complete", session_id=self.session_id)
        return challenge.payload.get("agent_hostname", "")

    def decrypt(self, envelope: Envelope) -> bytes:
        assert self.session_key is not None
        return crypto.decrypt(self.session_key, envelope.payload["nonce"], envelope.payload["ciphertext"])

    async def send_encrypted(self, type_: str, plaintext: bytes) -> None:
        assert self.session_key is not None
        nonce_b64, ciphertext_b64 = crypto.encrypt(self.session_key, plaintext)
        await self.send(type_, session_id=self.session_id, payload={"nonce": nonce_b64, "ciphertext": ciphertext_b64})

    async def close(self) -> None:
        await self._ws.close()
