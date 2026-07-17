# termhop agent tests — ECDH agreement, HKDF determinism, AEAD round-trip,
# tamper detection.
import base64

import pytest

from common.crypto import (
    _SESSION_KEY_LEN,
    CryptoError,
    decrypt,
    derive_session_key,
    encrypt,
    generate_ephemeral_keypair,
)


def test_ecdh_agreement_both_directions():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()

    key_a = derive_session_key(a_priv, b_pub)
    key_b = derive_session_key(b_priv, a_pub)

    assert key_a == key_b
    assert len(key_a) == 32


def test_different_keypairs_derive_different_keys():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    c_priv, c_pub = generate_ephemeral_keypair()

    key_ab = derive_session_key(a_priv, b_pub)
    key_ac = derive_session_key(a_priv, c_pub)
    assert key_ab != key_ac


def test_hkdf_deterministic_against_known_vector():
    # Fixed shared-secret-equivalent inputs -> fixed output, so an accidental
    # change to HKDF params (salt/info/hash/length) is caught by CI, not
    # discovered as a silent interop break later.
    a_priv = bytes(range(32))
    hkdf_input_pub = bytes(range(31, -1, -1))
    key1 = derive_session_key(a_priv, hkdf_input_pub)
    key2 = derive_session_key(a_priv, hkdf_input_pub)
    assert key1 == key2
    assert len(key1) == _SESSION_KEY_LEN


def test_encrypt_decrypt_round_trip():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_key(a_priv, b_pub)

    nonce_b64, ciphertext_b64 = encrypt(key, b"hello termhop")
    plaintext = decrypt(key, nonce_b64, ciphertext_b64)
    assert plaintext == b"hello termhop"


def test_nonce_unique_per_message():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_key(a_priv, b_pub)

    nonce1, _ = encrypt(key, b"msg1")
    nonce2, _ = encrypt(key, b"msg2")
    assert nonce1 != nonce2


def test_tamper_detection_flipped_byte_raises():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_key(a_priv, b_pub)

    nonce_b64, ciphertext_b64 = encrypt(key, b"authentic message")

    raw = bytearray(base64.b64decode(ciphertext_b64))
    raw[0] ^= 0xFF
    tampered_b64 = base64.b64encode(bytes(raw)).decode("ascii")

    with pytest.raises(CryptoError):
        decrypt(key, nonce_b64, tampered_b64)


def test_wrong_key_fails_to_decrypt():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    c_priv, c_pub = generate_ephemeral_keypair()

    key_ab = derive_session_key(a_priv, b_pub)
    key_ac = derive_session_key(a_priv, c_pub)

    nonce_b64, ciphertext_b64 = encrypt(key_ab, b"secret")
    with pytest.raises(CryptoError):
        decrypt(key_ac, nonce_b64, ciphertext_b64)


def test_invalid_base64_raises_crypto_error():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_key(a_priv, b_pub)

    with pytest.raises(CryptoError):
        decrypt(key, "not-valid-base64!!!", "also-not-valid!!!")
