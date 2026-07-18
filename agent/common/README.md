# agent/common

Shared session/protocol logic used by all three platform agents
(`../linux`, `../macos`, `../windows`). Status: built for the Linux agent's
needs (PROJECT_PLAN.md step 2) — envelope model, ECDH/HKDF/XChaCha20-
Poly1305 crypto, the pairing handshake state machine (`RelayClient`), the
`PTYBackend` abstract interface, config persistence, and the streaming pump
wiring a paired `RelayClient` to a `PTYBackend`.

- `envelope.py` — mirrors `relay-server/relay/envelope.py` field-for-field.
- `crypto.py` — authenticated protocol-v2 X25519/HKDF handshake, directional
  XChaCha20-Poly1305 keys, pairing proofs, and metadata-bound AEAD.
- `pairing.py` — agent-side routing token, out-of-band secret, and
  `session_id` generation (the relay never generates these — see PROTOCOL.md).
- `relay_client.py` — WS client + handshake state machine
  (`pair_init` → `pair_init_ack` → `pair_challenge` → `pair_complete`),
  tested against a real running relay-server instance.
- `ptybackend.py` — abstract PTY interface; `../linux/pty_backend.py` is the
  first concrete implementation.
- `session_pump.py` — wires a paired `RelayClient` to a `PTYBackend`:
  encrypts PTY output as `pty_data`, decrypts incoming `pty_input`.
- `cli.py` — shared pair-and-stream CLI used by all platform entry points.
- `config.py` — persists `relay.url` plus the post-pairing durable device
  credential under the platform config directory, including
  `$XDG_CONFIG_HOME/termhop` on Linux. POSIX config permissions are `0600`.

**Not yet implemented** (explicitly deferred past PROJECT_PLAN.md step 2):
`session_open`/`session_list`/multi-PTY session management, idle-detection
pattern matching and port forwarding.
