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
        self.session_keys: crypto.SessionKeys | None = None
        self.session_id: str | None = None
        self._transcript: bytes | None = None
        self._last_peer_encrypted_seq = 0

    @classmethod
    async def connect(cls, base_url: str) -> "FakeClientPeer":
        ws = await websockets.connect(f"{base_url}/ws/client")
        return cls(ws)

    async def send(
        self, type_: str, *, session_id: str | None = None, payload: dict | None = None
    ) -> None:
        self._seq += 1
        envelope = Envelope(
            v=2,
            type=type_,
            session_id=session_id,
            seq=self._seq,
            ts=int(time.time() * 1000),
            payload=payload or {},
        )
        await self._ws.send(envelope.model_dump_json())

    async def recv(self) -> Envelope:
        raw = await self._ws.recv()
        return parse_envelope(raw)

    async def pair_request_and_complete(
        self, token: str, pairing_secret: str, agent_pubkey_b64: str, session_id: str
    ) -> str:
        """Sends pair_request with a fresh ephemeral keypair, awaits
        pair_challenge, derives the session key, sends pair_complete.
        Returns the agent's hostname from pair_challenge.payload (proves
        the agent_hostname protocol addition round-trips end to end)."""
        self._own_private_key, own_pubkey_raw = crypto.generate_ephemeral_keypair()
        self.client_pubkey_b64 = crypto.encode_pubkey(own_pubkey_raw)
        self._transcript = crypto.handshake_transcript(
            session_id=session_id,
            token=token,
            agent_pubkey_b64=agent_pubkey_b64,
            client_pubkey_b64=self.client_pubkey_b64,
        )
        self.session_keys = crypto.derive_session_keys(
            self._own_private_key,
            crypto.decode_pubkey(agent_pubkey_b64),
            pairing_secret,
            self._transcript,
        )
        client_proof = crypto.pairing_proof(
            self.session_keys.proof, self._transcript, "client"
        )

        await self.send(
            "pair_request",
            payload={
                "token": token,
                "client_pubkey": self.client_pubkey_b64,
                "client_proof": client_proof,
            },
        )

        challenge = await self.recv()
        if challenge.type != "pair_challenge":
            raise AssertionError(
                f"expected pair_challenge, got {challenge.type}: {challenge.payload}"
            )

        assert challenge.payload["peer_pubkey"] == agent_pubkey_b64
        assert challenge.session_id == session_id
        self.session_id = challenge.session_id

        complete = await self.recv()
        assert complete.type == "pair_complete"
        assert crypto.verify_pairing_proof(
            self.session_keys.proof,
            self._transcript,
            "agent",
            complete.payload["agent_proof"],
        )
        return challenge.payload.get("agent_hostname", "")

    async def resume_request_and_complete(
        self, device_id: str, device_secret: str
    ) -> str:
        """Independently performs the saved-device side of mutual resume."""
        await self.send("resume_request", payload={"device_id": device_id})
        challenge = await self.recv()
        assert challenge.type == "resume_challenge"
        assert challenge.session_id is not None
        agent_pubkey = challenge.payload["agent_pubkey"]
        self.session_id = challenge.session_id
        self._own_private_key, own_pubkey_raw = crypto.generate_ephemeral_keypair()
        self.client_pubkey_b64 = crypto.encode_pubkey(own_pubkey_raw)
        self._transcript = crypto.handshake_transcript(
            session_id=self.session_id,
            token=f"resume:{device_id}",
            agent_pubkey_b64=agent_pubkey,
            client_pubkey_b64=self.client_pubkey_b64,
        )
        self.session_keys = crypto.derive_session_keys(
            self._own_private_key,
            crypto.decode_pubkey(agent_pubkey),
            device_secret,
            self._transcript,
        )
        proof = crypto.pairing_proof(
            self.session_keys.proof, self._transcript, "client"
        )
        await self.send(
            "resume_proof",
            session_id=self.session_id,
            payload={"client_pubkey": self.client_pubkey_b64, "client_proof": proof},
        )
        complete = await self.recv()
        assert complete.type == "resume_complete"
        assert crypto.verify_pairing_proof(
            self.session_keys.proof,
            self._transcript,
            "agent",
            complete.payload["agent_proof"],
        )
        return challenge.payload.get("agent_hostname", "")

    def decrypt(self, envelope: Envelope) -> bytes:
        assert self.session_keys is not None
        assert self.session_id is not None
        assert envelope.seq > self._last_peer_encrypted_seq
        aad = crypto.message_aad(
            type_=envelope.type,
            session_id=self.session_id,
            seq=envelope.seq,
            direction="agent_to_client",
        )
        plaintext = crypto.decrypt(
            self.session_keys.agent_to_client,
            envelope.payload["nonce"],
            envelope.payload["ciphertext"],
            aad=aad,
        )
        self._last_peer_encrypted_seq = envelope.seq
        return plaintext

    async def send_encrypted(self, type_: str, plaintext: bytes) -> None:
        assert self.session_keys is not None
        assert self.session_id is not None
        self._seq += 1
        seq = self._seq
        aad = crypto.message_aad(
            type_=type_,
            session_id=self.session_id,
            seq=seq,
            direction="client_to_agent",
        )
        nonce_b64, ciphertext_b64 = crypto.encrypt(
            self.session_keys.client_to_agent, plaintext, aad=aad
        )
        envelope = Envelope(
            v=2,
            type=type_,
            session_id=self.session_id,
            seq=seq,
            ts=int(time.time() * 1000),
            payload={"nonce": nonce_b64, "ciphertext": ciphertext_b64},
        )
        await self._ws.send(envelope.model_dump_json())

    async def close(self) -> None:
        await self._ws.close()
