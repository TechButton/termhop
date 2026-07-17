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
  "v": 1,
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
| `seq` | int | Monotonically increasing per-connection sequence number, used for ordering and idle-detection timing. |
| `ts` | int | Unix ms timestamp, set by sender. |
| `payload` | object | Type-specific. For encrypted types, this is `{ "nonce": "...", "ciphertext": "..." }` — the relay never inspects inside it. |

## Message Types

### Pairing (relay sees plaintext metadata, not session keys)

| `type` | Direction | Purpose |
|---|---|---|
| `pair_init` | agent → relay | Register a new pairing token + agent's ephemeral public key. |
| `pair_init_ack` | relay → agent | Confirms the relay has registered the pairing token. The agent must wait for this before displaying the QR/pairing link — otherwise a fast client `pair_request` can race ahead of the relay's own bookkeeping. |
| `pair_request` | client → relay | Client presents scanned/pasted pairing token. |
| `pair_challenge` | relay → both | Relay forwards each side's ephemeral public key to the other (opaque blob, relay doesn't generate or read key material). |
| `pair_complete` | agent/client → relay | Confirms handshake done; relay marks token consumed and invalid for reuse. |
| `error` | relay → either | Generic error response, `payload = {code, message}`. Sent for rejected pairing/rate-limit/protocol-validation failures; the connection is closed afterward for validation failures (oversized/malformed/version-mismatched envelopes), left open for recoverable ones (e.g. `token_invalid`). |

**Token and session-id ownership** — the relay never generates either:
- The relay never generates the pairing token (see SECURITY.md: "PC agent generates a single-use pairing token"). The agent generates it and sends it in `pair_init.payload.token`; the relay only validates format and atomically enforces single-use.
- The agent also generates the `session_id` itself and sends it in `pair_init.payload.session_id` — envelope-level `session_id` stays `null` for `pair_init`/`pair_request` (both are pre-pairing). The relay learns the session_id from the token record and includes it at the envelope level starting with `pair_challenge`, so the client learns it there and both sides address every later message by it.
- `pair_init.payload` = `{token, agent_pubkey, session_id, agent_hostname}`. `pair_request.payload` = `{token, client_pubkey}` — the relay forwards `client_pubkey` to the agent via `pair_challenge` and vice versa, so `pair_request` must carry the client's own ephemeral pubkey, not just the token. `pair_challenge.payload` = `{peer_pubkey, agent_hostname}` (the *other* side's pubkey; `agent_hostname` is only meaningful on the copy sent to the client, echoing what the agent reported at `pair_init` — GUI_SPEC.md's pairing screen shows "This device will be able to run commands on `<agent hostname>`", which needs a payload field to come from).
- Binary payload fields (`agent_pubkey`, `client_pubkey`, `peer_pubkey`, `nonce`, `ciphertext`) are standard base64-encoded ASCII strings (not urlsafe — these live inside JSON, not URLs).

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

- Handshake: X25519 ECDH between agent and client ephemeral keys, exchanged via `pair_challenge`. Derived shared secret feeds an HKDF to produce the session key.
- **KDF (pinned)**: HKDF-SHA256, `salt=None` (the X25519 shared secret already has full entropy; no multi-context separation need beyond `info`), `info=b"termhop-session-key-v1"` (version-tagged so a future protocol bump can derive a distinct key unambiguously), 32-byte output.
- **Data encryption (pinned)**: XChaCha20-Poly1305, IETF construction, per-message — chosen over AES-256-GCM since this project has no stated FIPS requirement, and XChaCha20's 192-bit extended nonce removes the nonce-uniqueness footgun of AES-GCM's 96-bit nonce over a long-lived streaming PTY connection emitting many small messages. `nonce` is 24 bytes, freshly random (`os.urandom`) per message — no counter state to persist across reconnects. Ciphertext includes the Poly1305 tag (libsodium's combined-mode API); no separate tag field.
- Long-term pairing: after first pairing, agent and client persist a long-term key pair per device so future connections skip QR re-scanning but still perform a fresh ECDH per session (forward secrecy). **Not yet implemented** — the reference Linux agent (agent/linux) only does ephemeral-per-session ECDH so far; every agent restart re-pairs from scratch until this lands.

Full rationale and threat model: see [`SECURITY.md`](./SECURITY.md).

## Versioning

- Envelope carries `v`. Relay and both endpoints should reject/negotiate down on mismatch rather than silently misparse.
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

- [x] Exact HKDF parameters and cipher suite — pinned above (HKDF-SHA256/XChaCha20-Poly1305), implemented in `agent/common/crypto.py`.
- [ ] Concrete chunk size and reassembly-hint fields for large PTY output bursts (relay-side cap is now fixed at 256 KiB; the sender-side chunking scheme itself is still open — the reference agent doesn't chunk yet, since a single PTY read is well under the cap in practice, but nothing enforces that for large output bursts).
- [ ] Whether `session_list` metadata (cwd, cmd) should be encrypted too, given it can leak project names/paths to the relay. Current draft leaves it plaintext for UI convenience — worth revisiting.
