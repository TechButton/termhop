// termhop client — session-key handshake and AEAD primitives, mirroring
// agent/common/crypto.py 1:1. No hand-rolled crypto: X25519 ECDH and
// XChaCha20-Poly1305 from @noble/curves/@noble/ciphers (audited, pure JS —
// same precisely-specified standards as the Python side's pynacl/libsodium
// binding, not a "different library" risk since these are RFC 7748/RFC 8439
// primitives). HKDF from the browser's native SubtleCrypto — RFC 5869
// like Python's `cryptography` HKDF.
//
// Pinned parameters (must match agent/common/crypto.py exactly):
//   - KDF: HKDF-SHA256, info="termhop-session-key-v1", 32-byte key.
//   - Salt: an EXPLICIT 32-byte all-zero buffer — NOT an empty Uint8Array.
//     Python's `cryptography` HKDF treats salt=None as an all-zero salt of
//     hash length (RFC 5869 §2.2); Web Crypto's HKDF has no "None" sentinel
//     and requires an explicit salt buffer. An empty salt is NOT equivalent
//     and produces a different key — verified against a cross-language
//     fixed vector in crypto.test.js, not just asserted here.
//   - AEAD: XChaCha20-Poly1305, 24-byte random nonce per message, combined
//     ciphertext+tag (matches libsodium's combined mode).
import { xchacha20poly1305 } from "@noble/ciphers/chacha";
import { x25519 } from "@noble/curves/ed25519";

const HKDF_INFO = new TextEncoder().encode("termhop-session-key-v1");
const HKDF_SALT = new Uint8Array(32); // explicit all-zero — see module docstring
const SESSION_KEY_LEN_BITS = 256;
const NONCE_LEN = 24;

export class CryptoError extends Error {}

export function generateEphemeralKeypair() {
  const privateKey = x25519.utils.randomSecretKey();
  const publicKey = x25519.getPublicKey(privateKey);
  return { privateKey, publicKey };
}

export async function deriveSessionKey(ownPrivateKey, peerPublicKey) {
  let sharedSecret;
  try {
    sharedSecret = x25519.getSharedSecret(ownPrivateKey, peerPublicKey);
  } catch (err) {
    throw new CryptoError(`ECDH failed: ${err.message}`);
  }

  const keyMaterial = await crypto.subtle.importKey("raw", sharedSecret, "HKDF", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "HKDF", hash: "SHA-256", salt: HKDF_SALT, info: HKDF_INFO },
    keyMaterial,
    SESSION_KEY_LEN_BITS
  );
  return new Uint8Array(bits);
}

export function encrypt(key, plaintext) {
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LEN));
  const cipher = xchacha20poly1305(key, nonce);
  const ciphertext = cipher.encrypt(plaintext);
  return { nonceB64: toBase64(nonce), ciphertextB64: toBase64(ciphertext) };
}

export function decrypt(key, nonceB64, ciphertextB64) {
  let nonce, ciphertext;
  try {
    nonce = fromBase64(nonceB64);
    ciphertext = fromBase64(ciphertextB64);
  } catch (err) {
    throw new CryptoError(`invalid base64 in encrypted payload: ${err.message}`);
  }

  try {
    const cipher = xchacha20poly1305(key, nonce);
    return cipher.decrypt(ciphertext);
  } catch (err) {
    throw new CryptoError(`decryption/authentication failed: ${err.message}`);
  }
}

export function encodePubkey(pubkeyRaw) {
  return toBase64(pubkeyRaw);
}

export function decodePubkey(pubkeyB64) {
  try {
    return fromBase64(pubkeyB64);
  } catch (err) {
    throw new CryptoError(`invalid base64 pubkey: ${err.message}`);
  }
}

function toBase64(bytes) {
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
