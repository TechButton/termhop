# TESTING.md — termhop

Not yet fleshed out — placeholder so `CONTRIBUTING.md`'s reference isn't
dangling. Fill this in alongside the first real implementation PRs.

## Planned coverage (track against this as components land)

- **`relay-server/`**: pairing-token lifecycle (issue, single-use,
  expiry), rate limiting, message routing between two connections,
  confirmation that stored/logged data never contains decrypted payloads.
- **`agent/common/`**: protocol message (de)serialization, session
  tracking state machine, idle-detection pattern matching — all testable
  without a real PTY.
- **`agent/linux` / `agent/macos` / `agent/windows`**: PTY spawn/attach,
  resize handling, process exit detection — platform-specific, run in CI
  on matching runners.
- **`client/`**: component-level tests for the screens' state machines
  (pairing status transitions, agent expand/collapse, form validation)
  now that they're real React components rather than prototype markup.
- **End-to-end**: agent <-> relay <-> client round trip against a local
  relay instance, once all three pieces exist.
- **Security-specific**: see the "Before First Public Release Checklist"
  in `SECURITY.md` — several of those items are tests, not just review
  steps (encryption-boundary audit, pairing token brute-force test).
