# agent/common

Shared session/protocol logic used by all three platform agents
(`../linux`, `../macos`, `../windows`). Status: built for the Linux agent's
needs (PROJECT_PLAN.md step 2) — envelope model, ECDH/HKDF/XChaCha20-
Poly1305 crypto, the pairing handshake state machine (`RelayClient`), the
`PTYBackend` abstract interface, config persistence, and the streaming pump
wiring a paired `RelayClient` to a `PTYBackend`.

- `envelope.py` — mirrors `relay-server/relay/envelope.py` field-for-field.
- `crypto.py` — X25519 ECDH + XChaCha20-Poly1305 via `pynacl`, HKDF via
  `cryptography` (pynacl has no first-class HKDF). No hand-rolled crypto.
- `pairing.py` — agent-side pairing token + `session_id` generation (the
  relay never generates either — see PROTOCOL.md).
- `relay_client.py` — WS client + handshake state machine
  (`pair_init` → `pair_init_ack` → `pair_challenge` → `pair_complete`),
  tested against a real running relay-server instance.
- `ptybackend.py` — abstract PTY interface; `../linux/pty_backend.py` is the
  first concrete implementation.
- `session_pump.py` — wires a paired `RelayClient` to a `PTYBackend`:
  encrypts PTY output as `pty_data`, decrypts incoming `pty_input`.
- `config.py` — persists `relay.url` to `~/.config/termhop/config.toml` (no
  keys yet — ephemeral-per-session only; long-term device keys are
  deliberately not built yet, see PROTOCOL.md's Encryption section).

**Not yet implemented** (explicitly deferred past PROJECT_PLAN.md step 2):
`session_open`/`session_list`/multi-PTY session management, idle-detection
pattern matching, port forwarding, persisted long-term device keypair.
