import { beforeEach, describe, expect, it, vi } from "vitest";
import { HandshakeError, HandshakeState, RelayClient } from "./relayClient.js";
import {
  decodePubkey,
  deriveSessionKeys,
  encodePubkey,
  encrypt,
  generateEphemeralKeypair,
  messageAad,
  pairingProof,
} from "./crypto.js";
import { buildEnvelope, dumpEnvelope, parseEnvelope } from "./envelope.js";

// Minimal fake WebSocket standing in for a real relay connection — lets us
// drive RelayClient's handshake state machine with canned envelope
// sequences without a real network/relay.
class FakeWebSocket {
  constructor(url) {
    this.url = url;
    this.sent = [];
    this._listeners = {};
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => this._emit("open"));
  }

  addEventListener(type, cb) {
    (this._listeners[type] ??= []).push(cb);
  }

  send(data) {
    this.sent.push(JSON.parse(data));
  }

  close() {
    this._emit("close");
  }

  _emit(type, event = {}) {
    for (const cb of this._listeners[type] ?? []) cb(event);
  }

  serverSend(envelopeObj) {
    this._emit("message", { data: JSON.stringify(envelopeObj) });
  }
}
FakeWebSocket.instances = [];

const PAIRING_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

function pairingFields(agentKeypair) {
  return {
    token: "tok_abc123",
    pairingSecret: PAIRING_SECRET,
    agentPubkey: encodePubkey(agentKeypair.publicKey),
    sessionId: "sess-1",
  };
}

async function agentProofFor(client) {
  return pairingProof(client.sessionKeys.proof, client._transcript, "agent");
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

describe("RelayClient handshake", () => {
  it("reconnects a saved device with fresh ephemeral keys and mutual proofs", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];
    const agent = generateEphemeralKeypair();
    const device = {
      deviceId: "dev-0123456789abcdef0123456789abcdef",
      deviceSecret: PAIRING_SECRET,
      relayUrl: "ws://localhost:8080",
      hostname: "saved-host",
    };
    await client.sendResumeRequest(device);
    const resumed = client.awaitResumeAndComplete();
    ws.serverSend({
      v: 2, type: "resume_challenge", session_id: "sess-resume", seq: 1, ts: Date.now(),
      payload: { agent_pubkey: encodePubkey(agent.publicKey), agent_hostname: "saved-host" },
    });
    await vi.waitFor(() => expect(ws.sent.at(-1).type).toBe("resume_proof"));
    ws.serverSend({
      v: 2, type: "resume_complete", session_id: "sess-resume", seq: 2, ts: Date.now(),
      payload: { agent_proof: await agentProofFor(client) },
    });
    await expect(resumed).resolves.toMatchObject({
      sessionId: "sess-resume", agentHostname: "saved-host",
    });
  });

  it("drives the full pair_request -> pair_challenge -> pair_complete sequence", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];

    const agentKeypair = generateEphemeralKeypair();
    const pairing = pairingFields(agentKeypair);
    await client.sendPairRequest(pairing);
    expect(ws.sent[0].type).toBe("pair_request");
    expect(ws.sent[0].payload.token).toBe("tok_abc123");
    expect(typeof ws.sent[0].payload.client_pubkey).toBe("string");

    const challengePromise = client.awaitPairChallengeAndComplete();
    ws.serverSend({
      v: 2,
      type: "pair_challenge",
      session_id: "sess-1",
      seq: 1,
      ts: Date.now(),
      payload: { peer_pubkey: pairing.agentPubkey, agent_hostname: "test-host" },
    });
    ws.serverSend({
      v: 2,
      type: "pair_complete",
      session_id: "sess-1",
      seq: 2,
      ts: Date.now(),
      payload: { agent_proof: await agentProofFor(client) },
    });
    const { sessionId, agentHostname, fingerprint } = await challengePromise;
    expect(sessionId).toBe("sess-1");
    expect(agentHostname).toBe("test-host");
    expect(fingerprint).toMatch(/^[0-9A-F]{4} [0-9A-F]{4} [0-9A-F]{4}$/);
    expect(client.sessionKeys.agentToClient).toBeInstanceOf(Uint8Array);

    // The agent's independently-derived key must match — proves the
    // client's ECDH math against the client's own ephemeral private key
    // (captured via the sent client_pubkey) agrees with the agent side.
    const clientPubRaw = decodePubkey(ws.sent[0].payload.client_pubkey);
    const agentSideKeys = await deriveSessionKeys(
      agentKeypair.privateKey, clientPubRaw, PAIRING_SECRET, client._transcript
    );
    expect(Array.from(agentSideKeys.agentToClient)).toEqual(Array.from(client.sessionKeys.agentToClient));
    expect(client.state).toBe(HandshakeState.PAIRED);
  });

  it("raises HandshakeError on a relay error envelope during pairing", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];

    const agent = generateEphemeralKeypair();
    await client.sendPairRequest({ ...pairingFields(agent), token: "bad-token" });
    const promise = client.awaitPairChallengeAndComplete();
    ws.serverSend({
      v: 2,
      type: "error",
      session_id: null,
      seq: 1,
      ts: Date.now(),
      payload: { code: "token_invalid", message: "token not found" },
    });
    await expect(promise).rejects.toThrow(HandshakeError);
  });

  it("raises HandshakeError on a malformed pair_challenge missing peer_pubkey", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];
    await client.sendPairRequest({ ...pairingFields(generateEphemeralKeypair()), token: "tok" });
    const promise = client.awaitPairChallengeAndComplete();
    ws.serverSend({ v: 2, type: "pair_challenge", session_id: "sess-1", seq: 1, ts: Date.now(), payload: {} });
    await expect(promise).rejects.toThrow(HandshakeError);
  });

  it("raises HandshakeError when the socket closes mid-handshake", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    await client.sendPairRequest({ ...pairingFields(generateEphemeralKeypair()), token: "tok" });
    const promise = client.awaitPairChallengeAndComplete();
    client.close();
    await expect(promise).rejects.toThrow(HandshakeError);
  });

  it("buffers a fast challenge and completion that arrive before a receive waiter", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];
    const pairing = pairingFields(generateEphemeralKeypair());
    await client.sendPairRequest(pairing);

    ws.serverSend({
      v: 2, type: "pair_challenge", session_id: "sess-1", seq: 1, ts: Date.now(),
      payload: { peer_pubkey: pairing.agentPubkey, agent_hostname: "fast-host" },
    });
    ws.serverSend({
      v: 2, type: "pair_complete", session_id: "sess-1", seq: 2, ts: Date.now(),
      payload: { agent_proof: await agentProofFor(client) },
    });

    await expect(client.awaitPairChallengeAndComplete()).resolves.toMatchObject({
      sessionId: "sess-1", agentHostname: "fast-host",
    });
  });

  it("rejects an agent key substituted by the relay", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];
    await client.sendPairRequest(pairingFields(generateEphemeralKeypair()));
    const promise = client.awaitPairChallengeAndComplete();
    ws.serverSend({
      v: 2, type: "pair_challenge", session_id: "sess-1", seq: 1, ts: Date.now(),
      payload: { peer_pubkey: encodePubkey(generateEphemeralKeypair().publicKey) },
    });
    await expect(promise).rejects.toThrow(/does not match the pairing link/);
  });
});

describe("RelayClient streaming", () => {
  async function pairedClient() {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];
    const agentKeypair = generateEphemeralKeypair();

    const pairing = { ...pairingFields(agentKeypair), token: "tok" };
    await client.sendPairRequest(pairing);
    const promise = client.awaitPairChallengeAndComplete();
    ws.serverSend({
      v: 2,
      type: "pair_challenge",
      session_id: "sess-1",
      seq: 1,
      ts: Date.now(),
      payload: { peer_pubkey: pairing.agentPubkey, agent_hostname: "host" },
    });
    ws.serverSend({
      v: 2,
      type: "pair_complete",
      session_id: "sess-1",
      seq: 2,
      ts: Date.now(),
      payload: { agent_proof: await agentProofFor(client) },
    });
    await promise;
    return { client, ws, agentKeypair };
  }

  it("accepts a durable credential only from the encrypted paired channel", async () => {
    const { client, ws } = await pairedClient();
    const credential = JSON.stringify({
      device_id: "dev-0123456789abcdef0123456789abcdef",
      device_secret: PAIRING_SECRET,
    });
    const aad = messageAad({
      type: "device_credential", sessionId: "sess-1", seq: 3, direction: "agent_to_client",
    });
    const encrypted = encrypt(client.sessionKeys.agentToClient, new TextEncoder().encode(credential), aad);
    const pending = client.awaitDeviceCredential();
    ws.serverSend({
      v: 2, type: "device_credential", session_id: "sess-1", seq: 3, ts: Date.now(),
      payload: { nonce: encrypted.nonceB64, ciphertext: encrypted.ciphertextB64 },
    });
    await expect(pending).resolves.toEqual({
      deviceId: "dev-0123456789abcdef0123456789abcdef", deviceSecret: PAIRING_SECRET,
    });
  });

  it("decrypts incoming pty_data and invokes onEncrypted", async () => {
    const { client, ws } = await pairedClient();
    const received = [];
    client.beginStreaming({ onEncrypted: (bytes) => received.push(new TextDecoder().decode(bytes)) });

    // Handshake test above already proves both sides derive the same key,
    // so encrypting with client.sessionKey stands in for "the agent sent
    // this" without needing to redo the agent-side ECDH here.
    const aad = messageAad({ type: "pty_data", sessionId: "sess-1", seq: 3, direction: "agent_to_client" });
    const { nonceB64, ciphertextB64 } = encrypt(
      client.sessionKeys.agentToClient, new TextEncoder().encode("hello from agent"), aad
    );
    ws.serverSend({
      v: 2,
      type: "pty_data",
      session_id: "sess-1",
      seq: 3,
      ts: Date.now(),
      payload: { nonce: nonceB64, ciphertext: ciphertextB64 },
    });

    expect(received).toEqual(["hello from agent"]);
  });

  it("sends encrypted pty_input the agent can decrypt", async () => {
    const { client, ws } = await pairedClient();
    client.beginStreaming({});

    client.sendEncrypted("pty_input", new TextEncoder().encode("echo hi\n"));
    const sent = ws.sent[ws.sent.length - 1];
    expect(sent.type).toBe("pty_input");
    expect(sent.session_id).toBe("sess-1");

    const { decrypt } = await import("./crypto.js");
    const aad = messageAad({
      type: sent.type, sessionId: sent.session_id, seq: sent.seq, direction: "client_to_agent",
    });
    const plaintext = decrypt(
      client.sessionKeys.clientToAgent, sent.payload.nonce, sent.payload.ciphertext, aad
    );
    expect(new TextDecoder().decode(plaintext)).toBe("echo hi\n");
  });

  it("sends terminal dimensions after a fit", async () => {
    const { client, ws } = await pairedClient();
    client.sendSessionResize(42, 132);
    expect(ws.sent.at(-1)).toMatchObject({
      type: "session_resize",
      session_id: "sess-1",
      payload: { rows: 42, cols: 132 },
    });
  });

  it("invokes onSessionClose when the peer closes the session", async () => {
    const { client, ws } = await pairedClient();
    let closedPayload = null;
    client.beginStreaming({ onSessionClose: (payload) => (closedPayload = payload) });

    ws.serverSend({
      v: 2,
      type: "session_close",
      session_id: "sess-1",
      seq: 3,
      ts: Date.now(),
      payload: { reason: "process_exited" },
    });
    expect(closedPayload).toEqual({ reason: "process_exited" });
  });

  it("buffers initial PTY output until the terminal registers streaming handlers", async () => {
    const { client, ws } = await pairedClient();
    const aad = messageAad({ type: "pty_data", sessionId: "sess-1", seq: 3, direction: "agent_to_client" });
    const encrypted = encrypt(
      client.sessionKeys.agentToClient, new TextEncoder().encode("early output"), aad
    );
    ws.serverSend({
      v: 2, type: "pty_data", session_id: "sess-1", seq: 3, ts: Date.now(),
      payload: { nonce: encrypted.nonceB64, ciphertext: encrypted.ciphertextB64 },
    });

    const received = [];
    client.beginStreaming({ onEncrypted: (bytes) => received.push(new TextDecoder().decode(bytes)) });
    expect(received).toEqual(["early output"]);
  });

  it("rejects replayed encrypted output", async () => {
    const { client, ws } = await pairedClient();
    const received = [];
    const errors = [];
    client.beginStreaming({
      onEncrypted: (bytes) => received.push(new TextDecoder().decode(bytes)),
      onError: (error) => errors.push(error),
    });
    const aad = messageAad({ type: "pty_data", sessionId: "sess-1", seq: 3, direction: "agent_to_client" });
    const encrypted = encrypt(client.sessionKeys.agentToClient, new TextEncoder().encode("once"), aad);
    const envelope = {
      v: 2, type: "pty_data", session_id: "sess-1", seq: 3, ts: Date.now(),
      payload: { nonce: encrypted.nonceB64, ciphertext: encrypted.ciphertextB64 },
    };
    ws.serverSend(envelope);
    ws.serverSend(envelope);
    expect(received).toEqual(["once"]);
    expect(errors[0].code).toBe("encrypted_message_rejected");
  });
});
