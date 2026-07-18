# PROTOCOL.md — termhop Wire Protocol

This document defines the message format used between agent↔relay and
relay↔client, so third parties can write alternative agents or clients without
reading the reference implementation. The relay only ever routes these
envelopes — it does not need to understand `payload` contents for encrypted
message types.

## Transport

- WebSocket (`wss://` only — no unencrypted `ws://` in any documented deployment).
- One WebSocket connection per agent-to-relay link, and one per client-to-relay link. The relay pairs them by `session_id`.

## Message Envelope

All messages are JSON objects with this shape:

```json
{
  "v": 2,
  "type": "string",
  "session_id": "string | null",
  "seq": 0,
  "ts": 1737100000000,
  "payload": {}
}
```

| Field | Type | Notes |
|---|---|---|
| `v` | int | Protocol version, for future compatibility. |
| `type` | string | Message type — see table below. |
| `session_id` | string \| null | Null only for pre-pairing handshake messages. |
| `seq` | int | Strictly increasing per sender connection. The relay rejects duplicates/regressions; endpoints additionally reject replayed encrypted messages. |
| `ts` | int | Unix ms timestamp, set by sender. |
| `payload` | object | Type-specific. For encrypted types, this is `{ "nonce": "...", "ciphertext": "..." }` — the relay never inspects inside it. |

## Message Types

### Pairing (relay sees plaintext metadata, not session keys)

| `type` | Direction | Purpose |
|---|---|---|
| `pair_init` | agent → relay | Register a new pairing token + agent's ephemeral public key. |
| `pair_init_ack` | relay → agent | Confirms the relay has registered the pairing token. The agent must wait for this before displaying the QR/pairing link — otherwise a fast client `pair_request` can race ahead of the relay's own bookkeeping. |
| `pair_request` | client → relay | Client presents the routing token, its ephemeral public key, and an out-of-band-secret-backed proof. |
| `pair_challenge` | relay → both | Relay forwards pinned public keys and the opaque client proof. |
| `pair_complete` | agent → relay → client | Agent confirms the client proof and returns its own proof; the client must validate it before streaming. |
| `resume_init` | agent → relay | Rebooted agent advertises a random device ID, new session ID, and fresh ephemeral key. |
| `resume_request` | client → relay → agent | Browser asks to reconnect a locally saved device ID. |
| `resume_challenge` | agent → relay → client | Agent supplies its fresh ephemeral key and hostname. |
| `resume_proof` | client → relay → agent | Client supplies its fresh key and durable-secret-backed proof. |
| `resume_complete` | agent → relay → client | Agent returns its proof; streaming begins only after client verification. |
| `device_credential` | agent → relay → client | First-pair-only encrypted delivery of the durable device ID/secret. Relay sees ciphertext only. |
| `error` | relay → either | Generic error response, `payload = {code, message}`. Sent for rejected pairing/rate-limit/protocol-validation failures; the connection is closed afterward for validation failures (oversized/malformed/version-mismatched envelopes), left open for recoverable ones (e.g. `token_invalid`). |

**Out-of-band pairing data and relay-visible routing data:**

- The agent generates a single-use routing `token`, a separate 256-bit `pairing_secret`, an ephemeral X25519 key pair, and `session_id`.
- The pairing URI carries `{relay, token, secret, agent_key, session, hostname}`. The secret, pinned agent key, and pinned session ID arrive at the client through the QR/pasted-link channel.
- Only `token`, `agent_pubkey`, `session_id`, and `agent_hostname` are sent in `pair_init`. The pairing secret is never sent to or stored by the relay. Redis keys contain `SHA-256(token)`, not the raw token.
- `pair_request.payload = {token, client_pubkey, client_proof}`. The proof authenticates the canonical transcript with a proof key derived from ECDH plus the out-of-band secret.
- The client rejects a `pair_challenge` whose agent key or session ID differs from the pairing link. The agent rejects an invalid `client_proof`.
- `pair_complete.payload = {agent_proof}`. The relay forwards it opaquely; the client validates it before entering the paired state.
- Once bound, a WebSocket may only address its own `session_id`. The relay rejects cross-session envelopes and duplicate role attachments.
- Public keys, nonces, ciphertext, and proofs use standard base64 inside JSON. The pairing secret uses unpadded URL-safe base64 in the URI.

### Session Control (relay sees these — routing only, no terminal content)

| `type` | Direction | Purpose |
|---|---|---|
| `session_list` | agent → relay → client | List of live/resumable sessions: `{pid, cwd, cmd, status, last_output_ts}[]`. Command strings here are metadata the agent chooses to expose, not full terminal content. |
| `session_open` | client → relay → agent | Request to attach to a session by ID. |
| `session_resize` | client → relay → agent | Terminal resize (rows/cols) — not sensitive, sent in the clear as routing metadata. |
| `session_close` | either → relay → other | Graceful session end. |
| `idle_alert` | agent → relay → client | Idle/permission-prompt notification trigger. Body should stay generic (see SECURITY.md) — no terminal content in the push payload itself. |

### Terminal Data (always encrypted — relay only sees ciphertext)

| `type` | Direction | Purpose |
|---|---|---|
| `pty_data` | agent → relay → client | PTY output bytes, encrypted. `payload = {nonce, ciphertext}`. |
| `pty_input` | client → relay → agent | Keystrokes/input bytes, encrypted, same envelope shape. |

### Port Forwarding (data encrypted; control metadata not)

| `type` | Direction | Purpose |
|---|---|---|
| `port_forward_request` | client → relay → agent | Request to open a forward for a given local port. |
| `port_forward_data` | either → relay → other | Encrypted tunneled bytes for the forwarded port. |
| `port_forward_close` | either → relay → other | Tear down the forward. |

## Encryption

- **Handshake:** X25519 ECDH between ephemeral endpoint keys. HKDF-SHA256 uses the 256-bit out-of-band pairing secret as salt and `b"termhop-handshake-v2\0" || SHA-256(transcript)` as info.
- **Canonical transcript:** `termhop-handshake-v2`, followed by newline-delimited `session_id`, routing `token`, `agent_pubkey`, and `client_pubkey` fields in that exact order. Both roles prove possession with HMAC-SHA256 over the transcript plus `role=client` or `role=agent`.
- **Directional keys:** HKDF produces 96 bytes, split into 32-byte `agent_to_client`, `client_to_agent`, and pairing-proof keys. A ciphertext from one direction therefore cannot be reflected into the other.
- **Data encryption:** XChaCha20-Poly1305, IETF construction, with a fresh random 24-byte nonce. Ciphertext includes the Poly1305 tag.
- **Associated data:** encrypted messages authenticate the exact direction, `type`, `session_id`, and `seq` using the canonical `termhop-message-v2` AAD encoding. Relabeling, cross-session delivery, direction reflection, and sequence modification fail authentication.
- **Replay handling:** relay connections require strictly increasing envelope sequence numbers. Endpoints track the last successfully authenticated encrypted sequence and reject duplicates or regressions even when the relay is considered malicious.
- Durable pairing: after initial pairing is mutually authenticated, the agent
  sends a separately generated random 256-bit device secret in an encrypted
  `device_credential` message. Both endpoints then persist it locally; it is
  never part of the pairing link.
  Reconnection performs fresh X25519 ECDH and uses that durable secret as the
  HKDF salt for role-bound proofs, retaining fresh traffic keys and forward
  secrecy. The relay sees only the random device routing ID and public data.
  The hosted account service never receives the durable secret.

Full rationale and threat model: see [`SECURITY.md`](./SECURITY.md).

## Versioning

- Envelope carries `v`. Protocol v2 endpoints reject mismatches rather than silently misparse; there is no automatic downgrade to v1.
- Breaking protocol changes bump `v`; additive fields (new optional keys) do not require a version bump.

## Message Size

The reference relay enforces a hard cap of 256 KiB (`MAX_ENVELOPE_BYTES`) on
the decoded size of any single envelope; a connection sending an oversized
envelope is closed with a policy-violation WS close code, not silently
truncated. Senders (agent/client) are responsible for splitting `pty_data`/
`port_forward_data` bytes across multiple sequential envelopes if their
buffer exceeds this cap — the relay does not reassemble chunks, it only
enforces the per-message ceiling.

## Open Questions (track in repo issues once public)

- [x] Exact authenticated handshake, directional HKDF parameters, AEAD associated data, and cipher suite — pinned above and covered by cross-language vectors.
- [ ] Concrete chunk size and reassembly-hint fields for large PTY output bursts (relay-side cap is now fixed at 256 KiB; the sender-side chunking scheme itself is still open — the reference agent doesn't chunk yet, since a single PTY read is well under the cap in practice, but nothing enforces that for large output bursts).
- [ ] Whether `session_list` metadata (cwd, cmd) should be encrypted too, given it can leak project names/paths to the relay. Current draft leaves it plaintext for UI convenience — worth revisiting.
- [ ] Before port forwarding is enabled, encrypt or authenticate its control messages as well as its byte stream; a malicious relay must not be able to request access to an arbitrary local port.

## Device and Session Architecture (next protocol phase)

Protocol v2 now has a durable device identity distinct from the fresh routing
session created for every attachment. The current agent still owns one PTY at a
time. A client disconnect or reboot can reconnect the device, but an OS reboot
necessarily destroys the PTY and starts a replacement shell. Multi-PTY session
IDs and resumable application-specific commands remain the next protocol phase.
