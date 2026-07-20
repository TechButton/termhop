# termhop agent — session-key handshake and AEAD primitives. No hand-rolled
# crypto: X25519 ECDH and XChaCha20-Poly1305 come from pynacl (libsodium
# bindings), HKDF comes from `cryptography` (pynacl has no first-class HKDF
# and hand-rolling one from raw HMAC would be error-prone). Each library is
# used for the primitive it implements directly.
#
# Pinned protocol-v2 parameters:
#   - ECDH: X25519 via nacl.bindings.crypto_scalarmult.
#   - Authentication: a 256-bit out-of-band pairing secret is the HKDF salt;
#     the canonical transcript hash is included in HKDF info.
#   - KDF output: independent agent->client, client->agent, and proof keys.
#   - AEAD: XChaCha20-Poly1305 (nacl.bindings, IETF construction), 24-byte
#     nonce plus AAD binding direction, type, session_id, and sequence.
import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

import nacl.bindings
import nacl.utils
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO_PREFIX = b"termhop-handshake-v2\x00"
_SESSION_KEY_LEN = 32  # bytes — required by crypto_aead_xchacha20poly1305_ietf
_KEY_MATERIAL_LEN = _SESSION_KEY_LEN * 3
_NONCE_LEN = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES


class CryptoError(Exception):
    pass


@dataclass(frozen=True)
class SessionKeys:
    agent_to_client: bytes
    client_to_agent: bytes
    proof: bytes


def generate_ephemeral_keypair() -> tuple[bytes, bytes]:
    """Returns (private_key_raw, public_key_raw), each 32 bytes."""
    private_key = nacl.utils.random(nacl.bindings.crypto_scalarmult_SCALARBYTES)
    public_key = nacl.bindings.crypto_scalarmult_base(private_key)
    return private_key, public_key


def handshake_transcript(
    *, session_id: str, token: str, agent_pubkey_b64: str, client_pubkey_b64: str
) -> bytes:
    """Canonical transcript shared byte-for-byte with client/src/lib/crypto.js."""
    return (
        "termhop-handshake-v2\n"
        f"session_id={session_id}\n"
        f"token={token}\n"
        f"agent_pubkey={agent_pubkey_b64}\n"
        f"client_pubkey={client_pubkey_b64}"
    ).encode("ascii")


def _decode_pairing_secret(pairing_secret: str) -> bytes:
    try:
        padding = "=" * (-len(pairing_secret) % 4)
        raw = base64.b64decode(pairing_secret + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"invalid pairing secret: {exc}") from exc
    if len(raw) != 32:
        raise CryptoError("pairing secret must decode to exactly 32 bytes")
    return raw


def derive_session_keys(
    own_private_key: bytes,
    peer_public_key: bytes,
    pairing_secret: str,
    transcript: bytes,
) -> SessionKeys:
    """Authenticated ECDH + HKDF -> directional traffic and proof keys."""
    if len(own_private_key) != 32 or len(peer_public_key) != 32:
        raise CryptoError("X25519 private and public keys must each be 32 bytes")
    try:
        shared_secret = nacl.bindings.crypto_scalarmult(own_private_key, peer_public_key)
    except Exception as exc:
        raise CryptoError(f"ECDH failed: {exc}") from exc

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_MATERIAL_LEN,
        salt=_decode_pairing_secret(pairing_secret),
        info=_HKDF_INFO_PREFIX + hashlib.sha256(transcript).digest(),
    )
    material = hkdf.derive(shared_secret)
    return SessionKeys(
        agent_to_client=material[:_SESSION_KEY_LEN],
        client_to_agent=material[_SESSION_KEY_LEN : _SESSION_KEY_LEN * 2],
        proof=material[_SESSION_KEY_LEN * 2 :],
    )


def pairing_proof(proof_key: bytes, transcript: bytes, role: str) -> str:
    if role not in {"agent", "client"}:
        raise CryptoError(f"invalid proof role: {role}")
    proof = hmac.new(proof_key, transcript + b"\nrole=" + role.encode("ascii"), hashlib.sha256).digest()
    return base64.b64encode(proof).decode("ascii")


def verify_pairing_proof(proof_key: bytes, transcript: bytes, role: str, proof_b64: str) -> bool:
    return hmac.compare_digest(pairing_proof(proof_key, transcript, role), proof_b64)


def message_aad(*, type_: str, session_id: str, seq: int, direction: str) -> bytes:
    if direction not in {"agent_to_client", "client_to_agent"}:
        raise CryptoError(f"invalid message direction: {direction}")
    return (
        "termhop-message-v2\n"
        f"direction={direction}\n"
        f"type={type_}\n"
        f"session_id={session_id}\n"
        f"seq={seq}"
    ).encode("ascii")


def encrypt(key: bytes, plaintext: bytes, *, aad: bytes) -> tuple[str, str]:
    """Returns (nonce_b64, ciphertext_b64). Ciphertext includes the
    Poly1305 tag (libsodium's combined-mode API) — no separate tag field."""
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext, aad, nonce, key
    )
    return base64.b64encode(nonce).decode("ascii"), base64.b64encode(ciphertext).decode("ascii")


def decrypt(key: bytes, nonce_b64: str, ciphertext_b64: str, *, aad: bytes) -> bytes:
    try:
        nonce = base64.b64decode(nonce_b64, validate=True)
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"invalid base64 in encrypted payload: {exc}") from exc
    if len(nonce) != _NONCE_LEN:
        raise CryptoError(f"nonce must decode to exactly {_NONCE_LEN} bytes")
    if len(ciphertext) < nacl.bindings.crypto_aead_xchacha20poly1305_ietf_ABYTES:
        raise CryptoError("ciphertext is shorter than the authentication tag")

    try:
        return nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
            ciphertext, aad, nonce, key
        )
    except Exception as exc:
        raise CryptoError(f"decryption/authentication failed: {exc}") from exc


def encode_pubkey(pubkey_raw: bytes) -> str:
    return base64.b64encode(pubkey_raw).decode("ascii")


def decode_pubkey(pubkey_b64: str) -> bytes:
    try:
        raw = base64.b64decode(pubkey_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"invalid base64 pubkey: {exc}") from exc
    if len(raw) != 32:
        raise CryptoError("public key must decode to exactly 32 bytes")
    return raw
