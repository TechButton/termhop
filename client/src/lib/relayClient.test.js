import { beforeEach, describe, expect, it, vi } from "vitest";
import { HandshakeError, HandshakeState, RelayClient } from "./relayClient.js";
import { generateEphemeralKeypair, decodePubkey, deriveSessionKey, encodePubkey, encrypt } from "./crypto.js";
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

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

describe("RelayClient handshake", () => {
  it("drives the full pair_request -> pair_challenge -> pair_complete sequence", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];

    await client.sendPairRequest("tok_abc123");
    expect(ws.sent[0].type).toBe("pair_request");
    expect(ws.sent[0].payload.token).toBe("tok_abc123");
    expect(typeof ws.sent[0].payload.client_pubkey).toBe("string");

    const agentKeypair = generateEphemeralKeypair();
    const agentPubB64 = encodePubkey(agentKeypair.publicKey);

    const challengePromise = client.awaitPairChallengeAndDeriveKey();
    ws.serverSend({
      v: 1,
      type: "pair_challenge",
      session_id: "sess-1",
      seq: 1,
      ts: Date.now(),
      payload: { peer_pubkey: agentPubB64, agent_hostname: "test-host" },
    });
    const { sessionId, agentHostname } = await challengePromise;
    expect(sessionId).toBe("sess-1");
    expect(agentHostname).toBe("test-host");
    expect(client.sessionKey).toBeInstanceOf(Uint8Array);

    // The agent's independently-derived key must match — proves the
    // client's ECDH math against the client's own ephemeral private key
    // (captured via the sent client_pubkey) agrees with the agent side.
    const clientPubRaw = decodePubkey(ws.sent[0].payload.client_pubkey);
    const agentSideKey = await deriveSessionKey(agentKeypair.privateKey, clientPubRaw);
    expect(Array.from(agentSideKey)).toEqual(Array.from(client.sessionKey));

    client.sendPairComplete();
    expect(ws.sent[1].type).toBe("pair_complete");
    expect(ws.sent[1].session_id).toBe("sess-1");
    expect(client.state).toBe(HandshakeState.PAIRED);
  });

  it("raises HandshakeError on a relay error envelope during pairing", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];

    await client.sendPairRequest("bad-token");
    const promise = client.awaitPairChallengeAndDeriveKey();
    ws.serverSend({
      v: 1,
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
    await client.sendPairRequest("tok");
    const promise = client.awaitPairChallengeAndDeriveKey();
    ws.serverSend({ v: 1, type: "pair_challenge", session_id: "sess-1", seq: 1, ts: Date.now(), payload: {} });
    await expect(promise).rejects.toThrow(HandshakeError);
  });

  it("raises HandshakeError when the socket closes mid-handshake", async () => {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    await client.sendPairRequest("tok");
    const promise = client.awaitPairChallengeAndDeriveKey();
    client.close();
    await expect(promise).rejects.toThrow(HandshakeError);
  });
});

describe("RelayClient streaming", () => {
  async function pairedClient() {
    const client = new RelayClient("ws://localhost:8080");
    await client.connect();
    const ws = FakeWebSocket.instances[0];
    const agentKeypair = generateEphemeralKeypair();

    await client.sendPairRequest("tok");
    const promise = client.awaitPairChallengeAndDeriveKey();
    ws.serverSend({
      v: 1,
      type: "pair_challenge",
      session_id: "sess-1",
      seq: 1,
      ts: Date.now(),
      payload: { peer_pubkey: encodePubkey(agentKeypair.publicKey), agent_hostname: "host" },
    });
    await promise;
    client.sendPairComplete();
    return { client, ws, agentKeypair };
  }

  it("decrypts incoming pty_data and invokes onEncrypted", async () => {
    const { client, ws } = await pairedClient();
    const received = [];
    client.beginStreaming({ onEncrypted: (bytes) => received.push(new TextDecoder().decode(bytes)) });

    // Handshake test above already proves both sides derive the same key,
    // so encrypting with client.sessionKey stands in for "the agent sent
    // this" without needing to redo the agent-side ECDH here.
    const { nonceB64, ciphertextB64 } = encrypt(client.sessionKey, new TextEncoder().encode("hello from agent"));
    ws.serverSend({
      v: 1,
      type: "pty_data",
      session_id: "sess-1",
      seq: 2,
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
    const plaintext = decrypt(client.sessionKey, sent.payload.nonce, sent.payload.ciphertext);
    expect(new TextDecoder().decode(plaintext)).toBe("echo hi\n");
  });

  it("invokes onSessionClose when the peer closes the session", async () => {
    const { client, ws } = await pairedClient();
    let closedPayload = null;
    client.beginStreaming({ onSessionClose: (payload) => (closedPayload = payload) });

    ws.serverSend({
      v: 1,
      type: "session_close",
      session_id: "sess-1",
      seq: 3,
      ts: Date.now(),
      payload: { reason: "process_exited" },
    });
    expect(closedPayload).toEqual({ reason: "process_exited" });
  });
});
