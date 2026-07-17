import { describe, expect, it } from "vitest";
import {
  CryptoError,
  decodePubkey,
  decrypt,
  deriveSessionKey,
  encodePubkey,
  encrypt,
  generateEphemeralKeypair,
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
const EXPECTED_KEY = "b441d46f00d1f9ceb0e3fd935db2c92beb2e7fb3b81c495a76dc6bdc288f931f";
const FIXED_NONCE_B64 = Buffer.from(hexToBytes("000102030405060708090a0b0c0d0e0f1011121314151617")).toString(
  "base64"
);
const FIXED_PLAINTEXT = "hello termhop cross-language test vector";
const EXPECTED_CIPHERTEXT_B64 = "xpvMEOXC4jAvPEs/fxzq/zhvOHhYFFFDUBNpcjRk/tnX2fFJ9Gcc1yPS9O2O5jVNtg8mTy4XtfU=";

describe("crypto cross-language fixed vector", () => {
  it("matches Python agent/common/crypto.py byte-for-byte", async () => {
    const priv = hexToBytes(FIXED_PRIV);
    const peerPriv = hexToBytes(FIXED_PEER_PRIV_SEED);
    const peerPub = x25519.getPublicKey(peerPriv);
    expect(bytesToHex(peerPub)).toBe(EXPECTED_PEER_PUB);

    const shared = x25519.getSharedSecret(priv, peerPub);
    expect(bytesToHex(shared)).toBe(EXPECTED_SHARED);

    const key = await deriveSessionKey(priv, peerPub);
    expect(bytesToHex(key)).toBe(EXPECTED_KEY);

    const nonce = Buffer.from(FIXED_NONCE_B64, "base64");
    const cipher = xchacha20poly1305(key, nonce);
    const ciphertext = cipher.encrypt(new TextEncoder().encode(FIXED_PLAINTEXT));
    expect(Buffer.from(ciphertext).toString("base64")).toBe(EXPECTED_CIPHERTEXT_B64);

    // and our own decrypt() must round-trip it back to the exact plaintext
    const plaintext = decrypt(key, FIXED_NONCE_B64, EXPECTED_CIPHERTEXT_B64);
    expect(new TextDecoder().decode(plaintext)).toBe(FIXED_PLAINTEXT);
  });
});

describe("crypto", () => {
  it("derives the same session key from both directions", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();

    const keyA = await deriveSessionKey(a.privateKey, b.publicKey);
    const keyB = await deriveSessionKey(b.privateKey, a.publicKey);

    expect(bytesToHex(keyA)).toBe(bytesToHex(keyB));
    expect(keyA.length).toBe(32);
  });

  it("different keypairs derive different keys", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const c = generateEphemeralKeypair();

    const keyAB = await deriveSessionKey(a.privateKey, b.publicKey);
    const keyAC = await deriveSessionKey(a.privateKey, c.publicKey);
    expect(bytesToHex(keyAB)).not.toBe(bytesToHex(keyAC));
  });

  it("encrypts and decrypts round-trip", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = await deriveSessionKey(a.privateKey, b.publicKey);

    const plaintext = new TextEncoder().encode("hello termhop");
    const { nonceB64, ciphertextB64 } = encrypt(key, plaintext);
    const decrypted = decrypt(key, nonceB64, ciphertextB64);
    expect(new TextDecoder().decode(decrypted)).toBe("hello termhop");
  });

  it("generates a unique nonce per message", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = await deriveSessionKey(a.privateKey, b.publicKey);

    const msg1 = encrypt(key, new TextEncoder().encode("msg1"));
    const msg2 = encrypt(key, new TextEncoder().encode("msg2"));
    expect(msg1.nonceB64).not.toBe(msg2.nonceB64);
  });

  it("detects tampered ciphertext", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const key = await deriveSessionKey(a.privateKey, b.publicKey);

    const { nonceB64, ciphertextB64 } = encrypt(key, new TextEncoder().encode("authentic message"));
    const tamperedBytes = Buffer.from(ciphertextB64, "base64");
    tamperedBytes[0] ^= 0xff;
    const tamperedB64 = tamperedBytes.toString("base64");

    expect(() => decrypt(key, nonceB64, tamperedB64)).toThrow(CryptoError);
  });

  it("fails to decrypt with the wrong key", async () => {
    const a = generateEphemeralKeypair();
    const b = generateEphemeralKeypair();
    const c = generateEphemeralKeypair();

    const keyAB = await deriveSessionKey(a.privateKey, b.publicKey);
    const keyAC = await deriveSessionKey(a.privateKey, c.publicKey);

    const { nonceB64, ciphertextB64 } = encrypt(keyAB, new TextEncoder().encode("secret"));
    expect(() => decrypt(keyAC, nonceB64, ciphertextB64)).toThrow(CryptoError);
  });

  it("round-trips a pubkey through base64 encode/decode", () => {
    const { publicKey } = generateEphemeralKeypair();
    const encoded = encodePubkey(publicKey);
    const decoded = decodePubkey(encoded);
    expect(bytesToHex(decoded)).toBe(bytesToHex(publicKey));
  });

  it("raises CryptoError on invalid base64", () => {
    expect(() => decodePubkey("!!!not-base64!!!")).toThrow(CryptoError);
    expect(() => decrypt(new Uint8Array(32), "!!!not-base64!!!", "!!!not-base64!!!")).toThrow(CryptoError);
  });
});
