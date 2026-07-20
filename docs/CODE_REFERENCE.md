# Code and script reference

This document explains what each executable area does and where its trust
boundary begins. Module headers provide the local implementation details.

## Relay server

- `relay/main.py`: creates FastAPI, Redis, and the in-memory connection registry;
  `/healthz` exposes release/protocol status without secrets.
- `relay/config.py`: parses and bounds environment settings. Protocol v2 is
  intentionally fixed; unsafe TTL, size, rate, Redis-scheme, and origin values
  fail startup.
- `relay/ws_handlers.py`: accepts role-specific WebSockets, enforces browser
  origins, message size/shape/version/sequence rules, handshake deadlines, and
  disconnect cleanup.
- `relay/router.py`: validates message roles and handshake fields, establishes
  pairing/resume state, and refuses terminal routing until endpoint proofs have
  completed. It forwards ciphertext but never decrypts it.
- `relay/pairing.py`: hashes routing tokens before Redis storage, atomically
  issues/consumes them, and tracks transient session state.
- `relay/ratelimit.py`: Redis Lua sliding-window and per-token attempt limits.
- `relay/session_registry.py`: live WebSocket/device routes and the explicit
  `pairing`/`resuming`/`established` phase boundary.
- `Dockerfile`, `docker-compose.yml`: non-root runtime, loopback publishing,
  Redis isolation, resource caps, and WebSocket transport-size cap.
- `termhop-relay.service`: hardened native systemd service for operators not
  using Docker.

## Agent

- `common/cli.py`: command parsing, initial pairing, saved-device resume,
  credential persistence, shell spawning, and clean interrupt handling.
- `common/relay_client.py`: outbound TLS WebSocket, protocol state machine,
  proof verification, AEAD envelopes, replay checks, and transport timeouts.
- `common/crypto.py`: X25519, HKDF-SHA256, proof HMAC, and
  XChaCha20-Poly1305. It validates encoded lengths before invoking primitives.
- `common/config.py`: OS-specific configuration and atomic owner-only secret
  writes. The durable device secret grants terminal access and is never sent
  to the account service.
- `common/session_pump.py`: two-way encrypted PTY pump and deterministic task,
  PTY, and WebSocket cleanup.
- `linux/pty_backend.py`, `macos/pty_backend.py`: asyncio-readable POSIX PTYs.
- `windows/pty_backend.py`: ConPTY with a daemon read bridge so cancellation
  cannot hang Python executor shutdown.
- OS `install.*` scripts: fast-forward source updates, isolated Python venvs,
  per-user launchers, and update-safe stop/restart behavior.
- systemd/launchd/Startup files: keep a saved agent connected without an
  interactive foreground terminal.

## Message flow

1. The agent creates a routing token, 256-bit out-of-band secret, ephemeral
   X25519 key, and session ID.
2. The relay stores only routing metadata. The `termhop://pair` link carries
   the secret and pinned key outside the relay connection.
3. Browser and agent derive directional keys and authenticate the canonical
   transcript. The relay cannot forge valid proofs.
4. Only after proof completion does the relay route encrypted terminal data.
5. Initial pairing transfers a separate durable device secret inside AEAD.
   Later resumes derive fresh ephemeral session keys from that secret.

## Non-goals and intentional power

The normal agent provides a terminal as the logged-in OS user. It is not a
command allowlist, malware sandbox, privilege boundary, or substitute for OS
account security. The disposable hosted demo is a separate restricted system.
