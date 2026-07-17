# TESTING.md — termhop

Not yet fleshed out — placeholder so `CONTRIBUTING.md`'s reference isn't
dangling. Fill this in alongside the first real implementation PRs.

## Coverage landed so far

- **`relay-server/`** (v1 built — 31 tests, `relay-server/tests/`):
  pairing-token lifecycle (issue/consume/expiry/reuse-rejection,
  `test_pairing_lifecycle.py`); per-IP and per-token rate limiting
  (`test_rate_limiting.py`); full pairing handshake + `pty_data`/`pty_input`
  round trip against a real running relay instance (`test_routing.py`);
  `session_list`/`session_open`/`session_resize`/`idle_alert` routing
  (`test_session_control.py`); `port_forward_*` routing
  (`test_port_forwarding.py`); oversized/malformed/version-mismatched
  envelope rejection (`test_message_limits.py`); and an automated canary-marker
  check that ciphertext content never reaches a log line or a Redis value
  (`test_no_plaintext_leak.py`, automates the SECURITY.md pre-release
  checklist item). Uses `redislite` (an embedded real `redis-server`) rather
  than a mock, so Lua-script atomicity is tested against real Redis
  semantics. Also manually smoke-tested via `docker compose build relay &&
  docker compose up -d` (real `redis:7-alpine`, not redislite) — full
  pairing→data→close round trip confirmed over a raw WS client against the
  containerized instance, with `redis-cli KEYS *` and `docker compose logs`
  checked for canary-marker absence post-session.

- **`agent/common/` + `agent/linux/`** (PROJECT_PLAN.md step 2 built —
  23 tests, `agent/tests/`): envelope round-trip
  (`test_envelope.py`); ECDH agreement, HKDF determinism against a fixed
  vector, encrypt/decrypt round-trip, tamper-detection, wrong-key rejection
  (`test_crypto.py`); the full pairing handshake — including the
  `agent_hostname` protocol addition — driven against a **real running
  relay-server instance** (booted as a subprocess in `agent/tests/conftest.py`)
  with a `FakeClientPeer` doing independent ECDH math, plus malformed-
  challenge/relay-error/mid-handshake-disconnect unhappy paths
  (`test_relay_client_handshake.py`); real PTY spawn/write/resize/exit-code/
  force-close (`test_pty_backend_linux.py`); and the literal step-2
  deliverable — real relay + real PTY + raw test client round trip
  (`test_end_to_end_linux.py`). Also manually verified via the actual
  `termhop-agent pair` CLI against a live relay-server instance, and the
  systemd user unit confirmed to load via `systemctl --user daemon-reload`.

## Planned coverage (track against this as components land)
- **`agent/common/` / `agent/linux`**: session tracking state machine for
  multi-PTY support, idle-detection pattern matching, port forwarding,
  persisted long-term device keypair — all deferred past step 2, see
  `agent/common/README.md`/`agent/linux/README.md` for exactly what's
  stubbed vs. real.
- **`agent/macos` / `agent/windows`**: PTY spawn/attach, resize handling,
  process exit detection — platform-specific, run in CI on matching
  runners.
- **`client/`**: component-level tests for the screens' state machines
  (pairing status transitions, agent expand/collapse, form validation)
  now that they're real React components rather than prototype markup.
- **End-to-end**: agent <-> relay <-> client round trip against a local
  relay instance, once all three pieces exist.
- **Security-specific**: see the "Before First Public Release Checklist"
  in `SECURITY.md` — several of those items are tests, not just review
  steps (encryption-boundary audit, pairing token brute-force test).
