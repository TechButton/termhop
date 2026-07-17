// termhop client — WebSocket client + pairing handshake (client role) +
// encrypted pty_data/pty_input pump. Mirrors agent/tests/fake_client_peer.py's
// sequencing (pair_request -> pair_challenge -> pair_complete), NOT
// agent/common/relay_client.py (that one plays the agent role). Field names
// match relay-server/relay/router.py exactly — the relay's code is the
// ground truth for wire compatibility, not just PROTOCOL.md's prose.
import { buildEnvelope, dumpEnvelope, parseEnvelope } from "./envelope.js";
import * as crypto from "./crypto.js";

export const HandshakeState = Object.freeze({
  IDLE: "idle",
  CONNECTING: "connecting",
  AWAITING_PAIR_CHALLENGE: "awaiting_pair_challenge",
  PAIRED: "paired",
  STREAMING: "streaming",
  CLOSED: "closed",
});

export class HandshakeError extends Error {}

export class RelayClient {
  constructor(relayUrl) {
    this._relayUrl = relayUrl.replace(/\/$/, "");
    this._ws = null;
    this._seq = 0;
    this._ownPrivateKey = null;
    this._pendingRecv = null;
    this._streamingHandlers = { onEncrypted: null, onSessionClose: null, onError: null };

    this.state = HandshakeState.IDLE;
    this.sessionId = null;
    this.sessionKey = null;
    this.agentHostname = "";
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.state = HandshakeState.CONNECTING;
      this._ws = new WebSocket(`${this._relayUrl}/ws/client`);
      this._ws.binaryType = "arraybuffer";
      this._ws.addEventListener("open", () => resolve(), { once: true });
      this._ws.addEventListener(
        "error",
        () => reject(new HandshakeError("WebSocket connection failed")),
        { once: true }
      );
      this._ws.addEventListener("message", (event) => this._onMessage(event), false);
      this._ws.addEventListener("close", () => this._onClose(), { once: true });
    });
  }

  _onMessage(event) {
    let envelope;
    try {
      envelope = parseEnvelope(event.data);
    } catch (err) {
      if (this._pendingRecv) {
        const { reject } = this._pendingRecv;
        this._pendingRecv = null;
        reject(err);
      }
      return;
    }

    if (this.state === HandshakeState.STREAMING) {
      this._dispatchStreaming(envelope);
      return;
    }

    if (this._pendingRecv) {
      const { resolve } = this._pendingRecv;
      this._pendingRecv = null;
      resolve(envelope);
    }
  }

  _onClose() {
    if (this._pendingRecv) {
      const { reject } = this._pendingRecv;
      this._pendingRecv = null;
      reject(new HandshakeError("WebSocket closed"));
    }
    this.state = HandshakeState.CLOSED;
  }

  _recv() {
    return new Promise((resolve, reject) => {
      this._pendingRecv = { resolve, reject };
    });
  }

  _send(type, { sessionId = null, payload = {} } = {}) {
    this._seq += 1;
    const envelope = buildEnvelope(type, { sessionId, seq: this._seq, payload });
    this._ws.send(dumpEnvelope(envelope));
  }

  async sendPairRequest(token) {
    const { privateKey, publicKey } = crypto.generateEphemeralKeypair();
    this._ownPrivateKey = privateKey;
    this.state = HandshakeState.AWAITING_PAIR_CHALLENGE;
    this._send("pair_request", { payload: { token, client_pubkey: crypto.encodePubkey(publicKey) } });
  }

  async awaitPairChallengeAndDeriveKey() {
    const envelope = await this._recv();
    if (envelope.type === "error") {
      throw new HandshakeError(`relay rejected pairing: ${JSON.stringify(envelope.payload)}`);
    }
    if (envelope.type !== "pair_challenge") {
      throw new HandshakeError(`expected pair_challenge, got ${envelope.type}`);
    }

    const peerPubkeyB64 = envelope.payload.peer_pubkey;
    if (!peerPubkeyB64) {
      throw new HandshakeError("pair_challenge missing payload.peer_pubkey");
    }

    const peerPubkeyRaw = crypto.decodePubkey(peerPubkeyB64);
    this.sessionKey = await crypto.deriveSessionKey(this._ownPrivateKey, peerPubkeyRaw);
    this.sessionId = envelope.session_id;
    this.agentHostname = envelope.payload.agent_hostname ?? "";

    return { sessionId: this.sessionId, agentHostname: this.agentHostname };
  }

  sendPairComplete() {
    this._send("pair_complete", { sessionId: this.sessionId });
    this.state = HandshakeState.PAIRED;
  }

  /** Call once pairing is complete, before streaming begins. */
  beginStreaming({ onEncrypted, onSessionClose, onError } = {}) {
    this._streamingHandlers = { onEncrypted, onSessionClose, onError };
    this.state = HandshakeState.STREAMING;
  }

  _dispatchStreaming(envelope) {
    if (envelope.type === "pty_data") {
      const plaintext = crypto.decrypt(this.sessionKey, envelope.payload.nonce, envelope.payload.ciphertext);
      this._streamingHandlers.onEncrypted?.(plaintext);
    } else if (envelope.type === "session_close") {
      this._streamingHandlers.onSessionClose?.(envelope.payload);
    } else if (envelope.type === "error") {
      this._streamingHandlers.onError?.(envelope.payload);
    }
  }

  sendEncrypted(type, plaintext) {
    const { nonceB64, ciphertextB64 } = crypto.encrypt(this.sessionKey, plaintext);
    this._send(type, { sessionId: this.sessionId, payload: { nonce: nonceB64, ciphertext: ciphertextB64 } });
  }

  sendSessionClose(reason = "") {
    this._send("session_close", { sessionId: this.sessionId, payload: { reason } });
  }

  close() {
    this._ws?.close();
    this.state = HandshakeState.CLOSED;
  }
}
