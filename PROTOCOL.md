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
| `pair_request` | client → relay | Client presents scanned/pasted pairing token. |
| `pair_challenge` | relay → both | Relay forwards each side's ephemeral public key to the other (opaque blob, relay doesn't generate or read key material). |
| `pair_complete` | agent/client → relay | Confirms handshake done; relay marks token consumed and invalid for reuse. |

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
- Data encryption: XChaCha20-Poly1305 (or AES-256-GCM if you'd rather stay in a FIPS-friendly primitive set) per-message, with `nonce` unique per message.
- Long-term pairing: after first pairing, agent and client persist a long-term key pair per device so future connections skip QR re-scanning but still perform a fresh ECDH per session (forward secrecy).

Full rationale and threat model: see [`SECURITY.md`](./SECURITY.md).

## Versioning

- Envelope carries `v`. Relay and both endpoints should reject/negotiate down on mismatch rather than silently misparse.
- Breaking protocol changes bump `v`; additive fields (new optional keys) do not require a version bump.

## Open Questions (track in repo issues once public)

- [ ] Exact HKDF parameters and cipher suite — pin before v1.0, not left as "pick one."
- [ ] Message size limits / chunking strategy for large PTY output bursts.
- [ ] Whether `session_list` metadata (cwd, cmd) should be encrypted too, given it can leak project names/paths to the relay. Current draft leaves it plaintext for UI convenience — worth revisiting.
