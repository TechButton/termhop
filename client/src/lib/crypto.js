// termhop client — session-key handshake and AEAD primitives, mirroring
// agent/common/crypto.py 1:1. No hand-rolled crypto: X25519 ECDH and
// XChaCha20-Poly1305 from @noble/curves/@noble/ciphers (audited, pure JS —
// same precisely-specified standards as the Python side's pynacl/libsodium
// binding, not a "different library" risk since these are RFC 7748/RFC 8439
// primitives). HKDF from the browser's native SubtleCrypto — RFC 5869
// like Python's `cryptography` HKDF.
//
// Pinned protocol-v2 parameters (must match agent/common/crypto.py exactly):
//   - KDF: HKDF-SHA256 with the 256-bit out-of-band pairing secret as salt
//     and the canonical transcript hash in info.
//   - Output: independent agent->client, client->agent, and proof keys.
//   - AEAD: XChaCha20-Poly1305, 24-byte random nonce per message, combined
//     ciphertext+tag, with direction/type/session/sequence bound as AAD.
import { xchacha20poly1305 } from "@noble/ciphers/chacha";
import { x25519 } from "@noble/curves/ed25519";

const HKDF_INFO_PREFIX = new TextEncoder().encode("termhop-handshake-v2\0");
const KEY_MATERIAL_LEN_BITS = 768;
const NONCE_LEN = 24;

export class CryptoError extends Error {}

export function generateEphemeralKeypair() {
  const privateKey = x25519.utils.randomSecretKey();
  const publicKey = x25519.getPublicKey(privateKey);
  return { privateKey, publicKey };
}

export function handshakeTranscript({ sessionId, token, agentPubkeyB64, clientPubkeyB64 }) {
  return new TextEncoder().encode(
    `termhop-handshake-v2\nsession_id=${sessionId}\ntoken=${token}\nagent_pubkey=${agentPubkeyB64}\nclient_pubkey=${clientPubkeyB64}`
  );
}

export async function deriveSessionKeys(ownPrivateKey, peerPublicKey, pairingSecret, transcript) {
  let sharedSecret;
  try {
    sharedSecret = x25519.getSharedSecret(ownPrivateKey, peerPublicKey);
  } catch (err) {
    throw new CryptoError(`ECDH failed: ${err.message}`);
  }

  const transcriptHash = new Uint8Array(await crypto.subtle.digest("SHA-256", transcript));
  const info = new Uint8Array(HKDF_INFO_PREFIX.length + transcriptHash.length);
  info.set(HKDF_INFO_PREFIX);
  info.set(transcriptHash, HKDF_INFO_PREFIX.length);
  const salt = fromBase64Url(pairingSecret);
  if (salt.length !== 32) throw new CryptoError("pairing secret must decode to exactly 32 bytes");

  const keyMaterial = await crypto.subtle.importKey("raw", sharedSecret, "HKDF", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "HKDF", hash: "SHA-256", salt, info },
    keyMaterial,
    KEY_MATERIAL_LEN_BITS
  );
  const material = new Uint8Array(bits);
  return {
    agentToClient: material.slice(0, 32),
    clientToAgent: material.slice(32, 64),
    proof: material.slice(64, 96),
  };
}

export async function pairingProof(proofKey, transcript, role) {
  if (role !== "agent" && role !== "client") throw new CryptoError(`invalid proof role: ${role}`);
  const suffix = new TextEncoder().encode(`\nrole=${role}`);
  const message = new Uint8Array(transcript.length + suffix.length);
  message.set(transcript);
  message.set(suffix, transcript.length);
  const hmacKey = await crypto.subtle.importKey("raw", proofKey, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return toBase64(new Uint8Array(await crypto.subtle.sign("HMAC", hmacKey, message)));
}

export async function verifyPairingProof(proofKey, transcript, role, proofB64) {
  const expected = fromBase64(await pairingProof(proofKey, transcript, role));
  const actual = fromBase64(proofB64);
  if (expected.length !== actual.length) return false;
  let different = 0;
  for (let i = 0; i < expected.length; i++) different |= expected[i] ^ actual[i];
  return different === 0;
}

export function messageAad({ type, sessionId, seq, direction }) {
  if (direction !== "agent_to_client" && direction !== "client_to_agent") {
    throw new CryptoError(`invalid message direction: ${direction}`);
  }
  return new TextEncoder().encode(
    `termhop-message-v2\ndirection=${direction}\ntype=${type}\nsession_id=${sessionId}\nseq=${seq}`
  );
}

export function encrypt(key, plaintext, aad) {
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LEN));
  const cipher = xchacha20poly1305(key, nonce, aad);
  const ciphertext = cipher.encrypt(plaintext);
  return { nonceB64: toBase64(nonce), ciphertextB64: toBase64(ciphertext) };
}

export function decrypt(key, nonceB64, ciphertextB64, aad) {
  let nonce, ciphertext;
  try {
    nonce = fromBase64(nonceB64);
    ciphertext = fromBase64(ciphertextB64);
  } catch (err) {
    throw new CryptoError(`invalid base64 in encrypted payload: ${err.message}`);
  }

  try {
    const cipher = xchacha20poly1305(key, nonce, aad);
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
    const key = fromBase64(pubkeyB64);
    if (key.length !== 32) throw new CryptoError("public key must decode to exactly 32 bytes");
    return key;
  } catch (err) {
    throw new CryptoError(`invalid base64 pubkey: ${err.message}`);
  }
}

export async function sessionFingerprint(sessionKeys, transcript) {
  if (!sessionKeys || !transcript) return null;
  const label = new TextEncoder().encode("termhop-session-fingerprint-v2\0");
  const material = new Uint8Array(label.length + transcript.length + 64);
  material.set(label);
  material.set(transcript, label.length);
  material.set(sessionKeys.agentToClient, label.length + transcript.length);
  material.set(sessionKeys.clientToAgent, label.length + transcript.length + 32);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", material));
  return Array.from(digest.slice(0, 6), (byte) => byte.toString(16).padStart(2, "0").toUpperCase())
    .join("")
    .match(/.{1,4}/g)
    .join(" ");
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

function fromBase64Url(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  return fromBase64(normalized + "=".repeat((4 - (normalized.length % 4)) % 4));
}
