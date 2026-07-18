# TESTING.md — termhop

## Local verification

```bash
cd relay-server
.venv/bin/pytest -q
.venv/bin/ruff check relay tests
.venv/bin/mypy relay

cd ../agent
.venv/bin/pytest -q
.venv/bin/ruff check common linux macos windows tests
.venv/bin/mypy common linux macos windows

cd ../client
npm ci
npm test
npm run build
```

Current local totals are 37 relay tests, 46 agent tests (41 passing on Linux
and 5 Windows-only skips), 39 client unit tests, and 2 Playwright E2E tests.

The relay and agent integration suites launch a real embedded Redis and a real
relay WebSocket server. The Linux end-to-end test connects an independently
implemented client peer, completes the authenticated protocol-v2 handshake,
drives a real PTY, and verifies encrypted input/output in both directions.

Security regression coverage includes:

- agent/client cross-language HKDF, proof, and XChaCha20-Poly1305 vectors;
- rejection of a client that lacks the out-of-band pairing secret;
- rejection of relay-substituted agent keys and session IDs;
- AEAD failure when ciphertext direction/type/session/sequence is changed;
- endpoint and relay replay/non-monotonic-sequence rejection;
- cross-session relay routing rejection;
- raw-token absence from Redis keys;
- plaintext-canary absence from relay logs and Redis values;
- fast WebSocket handshake and early-PTY buffering races.

## Continuous integration

`.github/workflows/ci.yml` runs the relay, Linux agent, and client suites plus
Ruff/mypy/build checks. Dedicated macOS and Windows jobs install their native
PTY dependencies and run the platform backend tests on matching hosted runners.

## Still required

- Independent cryptographic/protocol review before public production use.
- Real-hardware verification of macOS launchd and Windows Scheduled Task
  installation/lifecycle behavior.
- Durable-device, multi-session/resume, idle detection, notification, and port-
  forwarding tests as those features land.
- Browser component/E2E coverage for every fixture-driven management screen.
