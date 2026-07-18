// termhop client — WebSocket client + pairing handshake (client role) +
// encrypted pty_data/pty_input pump. Mirrors agent/tests/fake_client_peer.py's
// sequencing (pair_request -> pair_challenge -> pair_complete), NOT
// agent/common/relay_client.py (that one plays the agent role). Field names
// match relay-server/relay/router.py exactly — the relay's code is the
// ground truth for wire compatibility, not just PROTOCOL.md's prose.
import { buildEnvelope, dumpEnvelope, parseEnvelope } from "./envelope.js";
import * as crypto from "./crypto.js";

const PROTOCOL_VERSION = 2;

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
    this._inboundQueue = [];
    this._streamingHandlers = { onEncrypted: null, onSessionClose: null, onError: null };
    this._expectedAgentPubkey = "";
    this._expectedSessionId = "";
    this._transcript = null;
    this._clientProof = "";
    this._lastPeerEncryptedSeq = 0;

    this.state = HandshakeState.IDLE;
    this.sessionId = null;
    this.sessionKeys = null;
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
    if (envelope.v !== PROTOCOL_VERSION) {
      const err = new HandshakeError(
        `relay protocol version ${envelope.v} does not match client version ${PROTOCOL_VERSION}`
      );
      if (this._pendingRecv) {
        const { reject } = this._pendingRecv;
        this._pendingRecv = null;
        reject(err);
      } else {
        this._streamingHandlers.onError?.({ code: "version_mismatch", message: err.message });
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
    } else {
      this._inboundQueue.push(envelope);
    }
  }

  _onClose() {
    if (this._pendingRecv) {
      const { reject } = this._pendingRecv;
      this._pendingRecv = null;
      reject(new HandshakeError("WebSocket closed"));
    }
    const wasStreaming = this.state === HandshakeState.STREAMING;
    this.state = HandshakeState.CLOSED;
    if (wasStreaming) this._streamingHandlers.onDisconnected?.();
  }

  _recv() {
    if (this._inboundQueue.length > 0) {
      return Promise.resolve(this._inboundQueue.shift());
    }
    return new Promise((resolve, reject) => {
      this._pendingRecv = { resolve, reject };
    });
  }

  _send(type, { sessionId = null, payload = {} } = {}) {
    const seq = this._nextSeq();
    this._sendWithSeq(type, { sessionId, payload, seq });
    return seq;
  }

  _nextSeq() {
    this._seq += 1;
    return this._seq;
  }

  _sendWithSeq(type, { sessionId = null, payload = {}, seq }) {
    const envelope = buildEnvelope(type, { sessionId, seq, payload });
    this._ws.send(dumpEnvelope(envelope));
  }

  async sendPairRequest({ token, pairingSecret, agentPubkey, sessionId }) {
    const { privateKey, publicKey } = crypto.generateEphemeralKeypair();
    this._ownPrivateKey = privateKey;
    const clientPubkey = crypto.encodePubkey(publicKey);
    this._expectedAgentPubkey = agentPubkey;
    this._expectedSessionId = sessionId;
    this._transcript = crypto.handshakeTranscript({
      sessionId,
      token,
      agentPubkeyB64: agentPubkey,
      clientPubkeyB64: clientPubkey,
    });
    this.sessionKeys = await crypto.deriveSessionKeys(
      privateKey, crypto.decodePubkey(agentPubkey), pairingSecret, this._transcript
    );
    this._clientProof = await crypto.pairingProof(this.sessionKeys.proof, this._transcript, "client");
    this.state = HandshakeState.AWAITING_PAIR_CHALLENGE;
    this._send("pair_request", {
      payload: { token, client_pubkey: clientPubkey, client_proof: this._clientProof },
    });
  }

  async awaitPairChallengeAndComplete() {
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
    if (peerPubkeyB64 !== this._expectedAgentPubkey) {
      throw new HandshakeError("relay supplied an agent key that does not match the pairing link");
    }
    if (envelope.session_id !== this._expectedSessionId) {
      throw new HandshakeError("relay supplied a session_id that does not match the pairing link");
    }
    this.sessionId = envelope.session_id;
    this.agentHostname = envelope.payload.agent_hostname ?? "";

    const complete = await this._recv();
    if (complete.type === "error") {
      throw new HandshakeError(`relay rejected pairing: ${JSON.stringify(complete.payload)}`);
    }
    if (complete.type !== "pair_complete" || complete.session_id !== this.sessionId) {
      throw new HandshakeError(`expected pair_complete for this session, got ${complete.type}`);
    }
    const agentProof = complete.payload.agent_proof;
    if (!agentProof || !(await crypto.verifyPairingProof(
      this.sessionKeys.proof, this._transcript, "agent", agentProof
    ))) {
      throw new HandshakeError("agent pairing proof is invalid");
    }
    this.state = HandshakeState.PAIRED;
    const fingerprint = await crypto.sessionFingerprint(this.sessionKeys, this._transcript);
    return { sessionId: this.sessionId, agentHostname: this.agentHostname, fingerprint };
  }

  async awaitDeviceCredential() {
    const envelope = await this._recv();
    if (envelope.type !== "device_credential" || envelope.session_id !== this.sessionId) {
      throw new HandshakeError(`expected encrypted device_credential, got ${envelope.type}`);
    }
    const aad = crypto.messageAad({
      type: envelope.type,
      sessionId: this.sessionId,
      seq: envelope.seq,
      direction: "agent_to_client",
    });
    let credential;
    try {
      const plaintext = crypto.decrypt(
        this.sessionKeys.agentToClient,
        envelope.payload.nonce,
        envelope.payload.ciphertext,
        aad
      );
      credential = JSON.parse(new TextDecoder().decode(plaintext));
    } catch (error) {
      throw new HandshakeError(`invalid device credential: ${error.message}`);
    }
    if (!/^dev-[a-f0-9]{32}$/.test(credential.device_id || "")) {
      throw new HandshakeError("invalid durable device identifier");
    }
    // Reuse the strict 32-byte decoder used by pairing secrets by deriving a
    // throwaway key schedule would be wasteful; base64url shape and decoded
    // length are checked directly here before saving the credential.
    const normalized = (credential.device_secret || "").replace(/-/g, "+").replace(/_/g, "/");
    let decoded;
    try { decoded = atob(normalized + "=".repeat((4 - normalized.length % 4) % 4)); }
    catch { throw new HandshakeError("invalid durable device secret"); }
    if (decoded.length !== 32) throw new HandshakeError("durable device secret must contain 32 bytes");
    this._lastPeerEncryptedSeq = envelope.seq;
    return { deviceId: credential.device_id, deviceSecret: credential.device_secret };
  }

  async sendResumeRequest(device) {
    this._resumeDevice = device;
    this.state = HandshakeState.AWAITING_PAIR_CHALLENGE;
    this._send("resume_request", { payload: { device_id: device.deviceId } });
  }

  async awaitResumeAndComplete() {
    const challenge = await this._recv();
    if (challenge.type === "error") throw new HandshakeError(challenge.payload.message || challenge.payload.code);
    if (challenge.type !== "resume_challenge") {
      throw new HandshakeError(`expected resume_challenge, got ${challenge.type}`);
    }
    const agentPubkey = challenge.payload.agent_pubkey;
    crypto.decodePubkey(agentPubkey);
    this.sessionId = challenge.session_id;
    this.agentHostname = challenge.payload.agent_hostname || this._resumeDevice.hostname || "";
    const { privateKey, publicKey } = crypto.generateEphemeralKeypair();
    const clientPubkey = crypto.encodePubkey(publicKey);
    this._transcript = crypto.handshakeTranscript({
      sessionId: this.sessionId,
      token: `resume:${this._resumeDevice.deviceId}`,
      agentPubkeyB64: agentPubkey,
      clientPubkeyB64: clientPubkey,
    });
    this.sessionKeys = await crypto.deriveSessionKeys(
      privateKey, crypto.decodePubkey(agentPubkey), this._resumeDevice.deviceSecret, this._transcript
    );
    const clientProof = await crypto.pairingProof(this.sessionKeys.proof, this._transcript, "client");
    this._send("resume_proof", {
      sessionId: this.sessionId,
      payload: { client_pubkey: clientPubkey, client_proof: clientProof },
    });
    const complete = await this._recv();
    if (complete.type !== "resume_complete" || complete.session_id !== this.sessionId) {
      throw new HandshakeError(`expected resume_complete, got ${complete.type}`);
    }
    if (!(await crypto.verifyPairingProof(
      this.sessionKeys.proof, this._transcript, "agent", complete.payload.agent_proof || ""
    ))) {
      throw new HandshakeError("saved agent proof is invalid");
    }
    this.state = HandshakeState.PAIRED;
    return {
      sessionId: this.sessionId,
      agentHostname: this.agentHostname,
      fingerprint: await crypto.sessionFingerprint(this.sessionKeys, this._transcript),
    };
  }

  /** Call once pairing is complete, before streaming begins. */
  beginStreaming({ onEncrypted, onSessionClose, onError, onDisconnected } = {}) {
    this._streamingHandlers = { onEncrypted, onSessionClose, onError, onDisconnected };
    this.state = HandshakeState.STREAMING;
    const queued = this._inboundQueue.splice(0);
    for (const envelope of queued) this._dispatchStreaming(envelope);
  }

  _dispatchStreaming(envelope) {
    if (envelope.type === "pty_data") {
      try {
        if (envelope.session_id !== this.sessionId) throw new HandshakeError("encrypted envelope session mismatch");
        if (envelope.seq <= this._lastPeerEncryptedSeq) {
          throw new HandshakeError("replayed or out-of-order encrypted envelope");
        }
        const aad = crypto.messageAad({
          type: envelope.type,
          sessionId: this.sessionId,
          seq: envelope.seq,
          direction: "agent_to_client",
        });
        const plaintext = crypto.decrypt(
          this.sessionKeys.agentToClient,
          envelope.payload.nonce,
          envelope.payload.ciphertext,
          aad
        );
        this._lastPeerEncryptedSeq = envelope.seq;
        this._streamingHandlers.onEncrypted?.(plaintext);
      } catch (err) {
        this._streamingHandlers.onError?.({ code: "encrypted_message_rejected", message: err.message });
      }
    } else if (envelope.type === "session_close") {
      this._streamingHandlers.onSessionClose?.(envelope.payload);
    } else if (envelope.type === "error") {
      this._streamingHandlers.onError?.(envelope.payload);
    }
  }

  sendEncrypted(type, plaintext) {
    const seq = this._nextSeq();
    const aad = crypto.messageAad({
      type,
      sessionId: this.sessionId,
      seq,
      direction: "client_to_agent",
    });
    const { nonceB64, ciphertextB64 } = crypto.encrypt(
      this.sessionKeys.clientToAgent, plaintext, aad
    );
    this._sendWithSeq(type, {
      sessionId: this.sessionId,
      seq,
      payload: { nonce: nonceB64, ciphertext: ciphertextB64 },
    });
  }

  sendSessionResize(rows, cols) {
    if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows <= 0 || cols <= 0) return;
    this._send("session_resize", { sessionId: this.sessionId, payload: { rows, cols } });
  }

  sendSessionClose(reason = "") {
    this._send("session_close", { sessionId: this.sessionId, payload: { reason } });
  }

  close() {
    this._ws?.close();
    this.state = HandshakeState.CLOSED;
  }
}
