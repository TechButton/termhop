# termhop agent — session-key handshake and AEAD primitives. No hand-rolled
# crypto: X25519 ECDH and XChaCha20-Poly1305 come from pynacl (libsodium
# bindings), HKDF comes from `cryptography` (pynacl has no first-class HKDF
# and hand-rolling one from raw HMAC would violate the no-hand-rolled-crypto
# rule). Both libraries are the ones SECURITY.md names as acceptable; this
# uses each for the specific primitive it's strongest at.
#
# Pinned parameters (resolves PROTOCOL.md's HKDF/cipher "Open Questions"):
#   - ECDH: X25519 via nacl.bindings.crypto_scalarmult.
#   - KDF: HKDF-SHA256, salt=None, info=b"termhop-session-key-v1", 32-byte key.
#   - AEAD: XChaCha20-Poly1305 (nacl.bindings, IETF construction), 24-byte
#     nonce generated fresh via os.urandom per message — at 192 bits of
#     randomness there's no meaningful collision risk, so no counter state
#     needs to be persisted across reconnects.
#
# derive_session_key() takes only a raw shared secret — it has no knowledge
# of where the ephemeral keys came from, so a future persisted long-term
# device key can be layered in ahead of this function without reshaping it.
import base64
import os

import nacl.bindings
import nacl.utils
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO = b"termhop-session-key-v1"
_SESSION_KEY_LEN = 32  # bytes — required by crypto_aead_xchacha20poly1305_ietf
_NONCE_LEN = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES


class CryptoError(Exception):
    pass


def generate_ephemeral_keypair() -> tuple[bytes, bytes]:
    """Returns (private_key_raw, public_key_raw), each 32 bytes."""
    private_key = nacl.utils.random(nacl.bindings.crypto_scalarmult_SCALARBYTES)
    public_key = nacl.bindings.crypto_scalarmult_base(private_key)
    return private_key, public_key


def derive_session_key(own_private_key: bytes, peer_public_key: bytes) -> bytes:
    """ECDH + HKDF -> 32-byte symmetric session key."""
    try:
        shared_secret = nacl.bindings.crypto_scalarmult(own_private_key, peer_public_key)
    except Exception as exc:
        raise CryptoError(f"ECDH failed: {exc}") from exc

    hkdf = HKDF(algorithm=hashes.SHA256(), length=_SESSION_KEY_LEN, salt=None, info=_HKDF_INFO)
    return hkdf.derive(shared_secret)


def encrypt(key: bytes, plaintext: bytes) -> tuple[str, str]:
    """Returns (nonce_b64, ciphertext_b64). Ciphertext includes the
    Poly1305 tag (libsodium's combined-mode API) — no separate tag field."""
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext, None, nonce, key
    )
    return base64.b64encode(nonce).decode("ascii"), base64.b64encode(ciphertext).decode("ascii")


def decrypt(key: bytes, nonce_b64: str, ciphertext_b64: str) -> bytes:
    try:
        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
    except Exception as exc:
        raise CryptoError(f"invalid base64 in encrypted payload: {exc}") from exc

    try:
        return nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
            ciphertext, None, nonce, key
        )
    except Exception as exc:
        raise CryptoError(f"decryption/authentication failed: {exc}") from exc


def encode_pubkey(pubkey_raw: bytes) -> str:
    return base64.b64encode(pubkey_raw).decode("ascii")


def decode_pubkey(pubkey_b64: str) -> bytes:
    try:
        return base64.b64decode(pubkey_b64)
    except Exception as exc:
        raise CryptoError(f"invalid base64 pubkey: {exc}") from exc
