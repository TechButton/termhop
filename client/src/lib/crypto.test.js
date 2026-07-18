import { describe, expect, it } from "vitest";
import {
  CryptoError,
  decodePubkey,
  decrypt,
  deriveSessionKeys,
  encodePubkey,
  encrypt,
  generateEphemeralKeypair,
  handshakeTranscript,
  messageAad,
  pairingProof,
  verifyPairingProof,
} from "./crypto.js";
import { x25519 } from "@noble/curves/ed25519";
import { xchacha20poly1305 } from "@noble/ciphers/chacha";

const hexToBytes = (hex) => Uint8Array.from(Buffer.from(hex, "hex"));
const bytesToHex = (bytes) => Buffer.from(bytes).toString("hex");

// Fixed cross-language vector — generated once from agent/common/crypto.py
// with the exact same fixed inputs (see PR description / build notes), then
// pinned here. This is the actual interop proof: if HKDF salt handling,
// info string, or AEAD construction ever drift between the two languages,
// this test catches it — "we both used a standard" is not sufficient proof
// on its own.
const FIXED_PRIV = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f";
const FIXED_PEER_PRIV_SEED = "1f1e1d1c1b1a191817161514131211100f0e0d0c0b0a09080706050403020100";
const EXPECTED_PEER_PUB = "87968c1c1642bd0600f6ad869b88f92c9623d0dfc44f01deffe21c9add3dca5f";
const EXPECTED_SHARED = "dae0079aea6e6d02ca215a60d5d8f6689c3ed6009d41882b9181ff2481d9e27a";
const PAIRING_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const TRANSCRIPT = handshakeTranscript({
  sessionId: "sess-vector",
  token: "tok_vector",
  agentPubkeyB64: "agent-vector",
  clientPubkeyB64: "client-vector",
});
const EXPECTED_AGENT_TO_CLIENT = "5f612ec4669c3868e54f52dfd9f2d763c737f8f464df83addb4d8d03ea248340";
const EXPECTED_CLIENT_TO_AGENT = "01bed6fc5b13636ed0403d69d0aac39abc8be9fe05a65be1514786e14eac2eba";
const EXPECTED_PROOF_KEY = "93789c9b9c7f8c5ab477de242e0065abf2604b4bd8950c21019f84c65b781bd9";
const FIXED_NONCE_B64 = Buffer.from(hexToBytes("000102030405060708090a0b0c0d0e0f1011121314151617")).toString(
  "base64"
);
const FIXED_PLAINTEXT = "hello termhop cross-language test vector";
const EXPECTED_CIPHERTEXT_B64 = "FMTDqWdM+NCZcHkhl5pRXfhxExUvIA9kheXRca2fD7G2k32BG1H3aAXcr27puITeQvQXDXQi3gM=";
const VECTOR_AAD = messageAad({
  type: "pty_data", sessionId: "sess-vector", seq: 7, direction: "agent_to_client",
});

describe("crypto cross-language fixed vector", () => {
  it("matches Python agent/common/crypto.py byte-for-byte", async () => {
    const priv = hexToBytes(FIXED_PRIV);
    const peerPriv = hexToBytes(FIXED_PEER_PRIV_SEED);
    const peerPub = x25519.getPublicKey(peerPriv);
    expect(bytesToHex(peerPub)).toBe(EXPECTED_PEER_PUB);

    const shared = x25519.getSharedSecret(priv, peerPub);
    expect(bytesToHex(shared)).toBe(EXPECTED_SHARED);

    const keys = await deriveSessionKeys(priv, peerPub, PAIRING_SECRET, TRANSCRIPT);
    expect(bytesToHex(keys.agentToClient)).toBe(EXPECTED_AGENT_TO_CLIENT);
    expect(bytesToHex(keys.clientToAgent)).toBe(EXPECTED_CLIENT_TO_AGENT);
    expect(bytesToHex(keys.proof)).toBe(EXPECTED_PROOF_KEY);

    const nonce = Buffer.from(FIXED_NONCE_B64, "base64");
    const cipher = xchacha20poly1305(keys.agentToClient, nonce, VECTOR_AAD);
    const ciphertext = cipher.encrypt(new TextEncoder().encode(FIXED_PLAINTEXT));
    expect(Buffer.from(ciphertext).toString("base64")).toBe(EXPECTED_CIPHERTEXT_B64);

    // and our own decrypt() must round-trip it back to the exact plaintext
    const plaintext = decrypt(keys.agentToClient, FIXED_NONCE_B64, EXPECTED_CIPHERTEXT_B64, VECTOR_AAD);
    expect(new TextDecoder().decode(plaintext)).toBe(FIXED_PLAINTEXT);
  });
});

describe("crypto", () => {
  it("derives the same session key from both directions", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();

    const keyA = await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT);
    const keyB = await deriveSessionKeys(b.privateKey, a.publicKey, PAIRING_SECRET, TRANSCRIPT);

    expect(bytesToHex(keyA.agentToClient)).toBe(bytesToHex(keyB.agentToClient));
    expect(bytesToHex(keyA.agentToClient)).not.toBe(bytesToHex(keyA.clientToAgent));
  });

  it("different keypairs derive different keys", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const c = generateEphemeralKeypair();

    const keyAB = await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT);
    const keyAC = await deriveSessionKeys(a.privateKey, c.publicKey, PAIRING_SECRET, TRANSCRIPT);
    expect(bytesToHex(keyAB.agentToClient)).not.toBe(bytesToHex(keyAC.agentToClient));
  });

  it("encrypts and decrypts round-trip", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = (await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT)).agentToClient;

    const plaintext = new TextEncoder().encode("hello termhop");
    const { nonceB64, ciphertextB64 } = encrypt(key, plaintext, VECTOR_AAD);
    const decrypted = decrypt(key, nonceB64, ciphertextB64, VECTOR_AAD);
    expect(new TextDecoder().decode(decrypted)).toBe("hello termhop");
  });

  it("generates a unique nonce per message", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = (await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT)).agentToClient;

    const msg1 = encrypt(key, new TextEncoder().encode("msg1"), VECTOR_AAD);
    const msg2 = encrypt(key, new TextEncoder().encode("msg2"), VECTOR_AAD);
    expect(msg1.nonceB64).not.toBe(msg2.nonceB64);
  });

  it("detects tampered ciphertext", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = (await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT)).agentToClient;

    const { nonceB64, ciphertextB64 } = encrypt(key, new TextEncoder().encode("authentic message"), VECTOR_AAD);
    const tamperedBytes = Buffer.from(ciphertextB64, "base64");
    tamperedBytes[0] ^= 0xff;
    const tamperedB64 = tamperedBytes.toString("base64");

    expect(() => decrypt(key, nonceB64, tamperedB64, VECTOR_AAD)).toThrow(CryptoError);
  });

  it("fails to decrypt with the wrong key", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const c = generateEphemeralKeypair();

    const keyAB = (await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT)).agentToClient;
    const keyAC = (await deriveSessionKeys(a.privateKey, c.publicKey, PAIRING_SECRET, TRANSCRIPT)).agentToClient;

    const { nonceB64, ciphertextB64 } = encrypt(keyAB, new TextEncoder().encode("secret"), VECTOR_AAD);
    expect(() => decrypt(keyAC, nonceB64, ciphertextB64, VECTOR_AAD)).toThrow(CryptoError);
  });

  it("round-trips a pubkey through base64 encode/decode", () => {
    const { publicKey } = generateEphemeralKeypair();
    const encoded = encodePubkey(publicKey);
    const decoded = decodePubkey(encoded);
    expect(bytesToHex(decoded)).toBe(bytesToHex(publicKey));
  });

  it("raises CryptoError on invalid base64", () => {
    expect(() => decodePubkey("!!!not-base64!!!")).toThrow(CryptoError);
    expect(() => decrypt(new Uint8Array(32), "!!!not-base64!!!", "!!!not-base64!!!", VECTOR_AAD)).toThrow(CryptoError);
  });

  it("authenticates message type, direction, session, and sequence", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = (await deriveSessionKeys(a.privateKey, b.publicKey, PAIRING_SECRET, TRANSCRIPT)).agentToClient;
    const encrypted = encrypt(key, new TextEncoder().encode("output"), VECTOR_AAD);
    const reflected = messageAad({
      type: "pty_input", sessionId: "sess-vector", seq: 7, direction: "client_to_agent",
    });
    expect(() => decrypt(key, encrypted.nonceB64, encrypted.ciphertextB64, reflected)).toThrow(CryptoError);
  });

  it("creates role-bound pairing proofs", async () => {
    const proofKey = hexToBytes(EXPECTED_PROOF_KEY);
    const proof = await pairingProof(proofKey, TRANSCRIPT, "client");
    expect(proof).toBe("5g/LOjn8225D3Umt113de69njYbJWO46uC8Xc2gamWI=");
    expect(await verifyPairingProof(proofKey, TRANSCRIPT, "client", proof)).toBe(true);
    expect(await verifyPairingProof(proofKey, TRANSCRIPT, "agent", proof)).toBe(false);
  });
});
