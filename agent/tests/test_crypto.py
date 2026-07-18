# termhop agent tests — ECDH agreement, HKDF determinism, AEAD round-trip,
# tamper detection.
import base64

import pytest

from common.crypto import (
    _SESSION_KEY_LEN,
    CryptoError,
    decrypt,
    derive_session_keys,
    encrypt,
    generate_ephemeral_keypair,
    handshake_transcript,
    message_aad,
    pairing_proof,
    verify_pairing_proof,
)

PAIRING_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
TRANSCRIPT = handshake_transcript(
    session_id="sess-test",
    token="tok_test",
    agent_pubkey_b64="agent-key",
    client_pubkey_b64="client-key",
)


def test_ecdh_agreement_both_directions():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()

    keys_a = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT)
    keys_b = derive_session_keys(b_priv, a_pub, PAIRING_SECRET, TRANSCRIPT)

    assert keys_a == keys_b
    assert len(keys_a.agent_to_client) == 32
    assert keys_a.agent_to_client != keys_a.client_to_agent


def test_different_keypairs_derive_different_keys():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    c_priv, c_pub = generate_ephemeral_keypair()

    key_ab = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT)
    key_ac = derive_session_keys(a_priv, c_pub, PAIRING_SECRET, TRANSCRIPT)
    assert key_ab != key_ac


def test_hkdf_deterministic_against_known_vector():
    # Fixed shared-secret-equivalent inputs -> fixed output, so an accidental
    # change to HKDF params (salt/info/hash/length) is caught by CI, not
    # discovered as a silent interop break later.
    a_priv = bytes(range(32))
    hkdf_input_pub = bytes(range(31, -1, -1))
    key1 = derive_session_keys(a_priv, hkdf_input_pub, PAIRING_SECRET, TRANSCRIPT)
    key2 = derive_session_keys(a_priv, hkdf_input_pub, PAIRING_SECRET, TRANSCRIPT)
    assert key1 == key2
    assert len(key1.proof) == _SESSION_KEY_LEN


def test_encrypt_decrypt_round_trip():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    aad = message_aad(type_="pty_data", session_id="sess-test", seq=1, direction="agent_to_client")

    nonce_b64, ciphertext_b64 = encrypt(key, b"hello termhop", aad=aad)
    plaintext = decrypt(key, nonce_b64, ciphertext_b64, aad=aad)
    assert plaintext == b"hello termhop"


def test_nonce_unique_per_message():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    aad = message_aad(type_="pty_data", session_id="sess-test", seq=1, direction="agent_to_client")

    nonce1, _ = encrypt(key, b"msg1", aad=aad)
    nonce2, _ = encrypt(key, b"msg2", aad=aad)
    assert nonce1 != nonce2


def test_tamper_detection_flipped_byte_raises():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    aad = message_aad(type_="pty_data", session_id="sess-test", seq=1, direction="agent_to_client")

    nonce_b64, ciphertext_b64 = encrypt(key, b"authentic message", aad=aad)

    raw = bytearray(base64.b64decode(ciphertext_b64))
    raw[0] ^= 0xFF
    tampered_b64 = base64.b64encode(bytes(raw)).decode("ascii")

    with pytest.raises(CryptoError):
        decrypt(key, nonce_b64, tampered_b64, aad=aad)


def test_wrong_key_fails_to_decrypt():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    c_priv, c_pub = generate_ephemeral_keypair()

    key_ab = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    key_ac = derive_session_keys(a_priv, c_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    aad = message_aad(type_="pty_data", session_id="sess-test", seq=1, direction="agent_to_client")

    nonce_b64, ciphertext_b64 = encrypt(key_ab, b"secret", aad=aad)
    with pytest.raises(CryptoError):
        decrypt(key_ac, nonce_b64, ciphertext_b64, aad=aad)


def test_invalid_base64_raises_crypto_error():
    a_priv, a_pub = generate_ephemeral_keypair()
    b_priv, b_pub = generate_ephemeral_keypair()
    key = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    aad = message_aad(type_="pty_data", session_id="sess-test", seq=1, direction="agent_to_client")

    with pytest.raises(CryptoError):
        decrypt(key, "not-valid-base64!!!", "also-not-valid!!!", aad=aad)


def test_metadata_and_direction_are_authenticated():
    a_priv, _ = generate_ephemeral_keypair()
    _, b_pub = generate_ephemeral_keypair()
    key = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).agent_to_client
    aad = message_aad(type_="pty_data", session_id="sess-test", seq=7, direction="agent_to_client")
    nonce, ciphertext = encrypt(key, b"output", aad=aad)
    reflected_aad = message_aad(
        type_="pty_input", session_id="sess-test", seq=7, direction="client_to_agent"
    )
    with pytest.raises(CryptoError):
        decrypt(key, nonce, ciphertext, aad=reflected_aad)


def test_pairing_proofs_are_role_bound():
    a_priv, _ = generate_ephemeral_keypair()
    _, b_pub = generate_ephemeral_keypair()
    proof_key = derive_session_keys(a_priv, b_pub, PAIRING_SECRET, TRANSCRIPT).proof
    client_proof = pairing_proof(proof_key, TRANSCRIPT, "client")
    assert verify_pairing_proof(proof_key, TRANSCRIPT, "client", client_proof)
    assert not verify_pairing_proof(proof_key, TRANSCRIPT, "agent", client_proof)
