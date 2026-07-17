# agent/common

Shared session/protocol logic used by all three platform agents
(`../linux`, `../macos`, `../windows`).

Not yet implemented. Scope per `../../PROJECT_PLAN.md`:

- WebSocket client that dials out to the relay (outbound-only — no
  inbound listener, on any platform).
- ECDH handshake + session encryption (see `../../SECURITY.md`).
- Session tracking (PID, cwd, launch command, last-output timestamp) and
  the `session_list`/`session_open`/`session_resize`/`session_close`
  message handling from `../../PROTOCOL.md`.
- Idle/permission-prompt pattern detection for push-notification triggers.
